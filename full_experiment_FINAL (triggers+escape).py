import psychopy 
psychopy.useVersion('2023.1.3')
import pandas as pd 
import os, random
from psychopy import sound, visual, core, event, gui, parallel
import serial 

# ==============================================================================
# EEG TRIGGER SETUP
# ==============================================================================
# Try serial port first, then parallel port, then fall back to print-only.
# Change "COM4" and 0x0378 to match your lab setup.

try:
    port = serial.Serial("COM4", 115200)
    port_type = 'serial'
except Exception:
    try:
        port = parallel.ParallelPort(0x0378)
        port_type = 'parallel'
    except Exception:
        port = None
        port_type = 'none'

print(f'EEG port type: {port_type}')

def trigger(code):
    """Send an EEG trigger code and immediately reset to 0."""
    if port_type == 'serial':
        port.write(code.to_bytes(1, 'big'))
    elif port_type == 'parallel':
        port.setData(code)
        core.wait(0.020)   # 20 ms pulse width
        port.setData(0)
    print(f'Trigger sent: {code}')

# ------------------------------------------------------------------------------
# TRIGGER CODE TABLE
# ------------------------------------------------------------------------------
# Trial Start
TRIG_GO_SOUND       = 11   # go-beep plays

# Sound/tactile triggers — one code per distance threshold
# The seven thresholds are ordered from far to near (605 → 40 px from target)
# Each sound trigger also corresponds to a tactile zone in the PS condition
TRIG_SOUND_TRAINING = {
    605: 40,   # zone 1 (farthest)  — short-swoosh soft
    525: 41,   # zone 2             — slide
    375: 42,   # zone 3             — short-swoosh louder
    300: 43,   # zone 4             — thud
    210: 44,   # zone 5             — match
    145: 45,   # zone 6             — thud softer
     40: 46,   # zone 7 (nearest)   — slide_target
}

TRIG_SOUND_TRANSITION = {
    605: 50,   # zone 1 (farthest)  — short-swoosh soft
    525: 51,   # zone 2             — slide
    375: 52,   # zone 3             — short-swoosh louder
    300: 53,   # zone 4             — thud
    210: 54,   # zone 5             — match
    145: 55,   # zone 6             — thud softer
     40: 56,   # zone 7 (nearest)   — slide_target
}

TRIG_SOUND_TEST = {
    605: 60,   # zone 1 (farthest)  — short-swoosh soft
    525: 61,   # zone 2             — slide
    375: 62,   # zone 3             — short-swoosh louder
    300: 63,   # zone 4             — thud
    210: 64,   # zone 5             — match
    145: 65,   # zone 6             — thud softer
     40: 66,   # zone 7 (nearest)   — slide_target
}

# ==============================================================================
# SUBJECT ID
# ==============================================================================
ID_box = gui.Dlg(title='Subject identity')
ID_box.addField('ID: ', '')
ID_box.addField(
    'Block order:',
    choices=['1', '2', '1-2']
)
ok = ID_box.show()
sub_id = ok[0]
order_str = ok[1]
block_order = list(map(int, order_str.split('-')))

# ==============================================================================
# SCREEN SETUP
# ==============================================================================
win = visual.Window(
    fullscr=True,
    color="black",
    units='pix'
)

all_trials_data = []

# ==============================================================================
# SAFE ESCAPE
# ==============================================================================
class EscapePressed(Exception):
    pass


def safe_quit(reason="escape"):
    print(f"\n[safe_quit] called — reason: {reason}")

    if all_trials_data:
        try:
            full_df = pd.concat(all_trials_data, ignore_index=True)
            save_path = "data/"
            os.makedirs(save_path, exist_ok=True)
            filename = save_path + f"mouse_tracking_{sub_id}_ESCAPED.csv"
            full_df.to_csv(filename, index=False)
            print(f"[safe_quit] Partial data saved to: {filename}")
        except Exception as e:
            print(f"[safe_quit] Could not save data: {e}")
    else:
        print("[safe_quit] No trial data collected — nothing to save.")

    if port_type == 'serial' and port is not None:
        try:
            port.close()
        except Exception:
            pass

    try:
        win.close()
    except Exception:
        pass

    core.quit()


def check_escape(keys):
    if 'escape' in keys:
        raise EscapePressed()


def wait_keys_safe(keyList=None):
    """Drop-in replacement for event.waitKeys() that raises on escape."""
    keys = event.waitKeys(keyList=keyList)
    if keys is None:
        keys = []
    check_escape(keys)
    return keys


# ==============================================================================
# BLOCK / PHASE DESIGN TABLE
# ==============================================================================
design = [
    {"block": 1, "phase": "training",    "condition": "AS+PS",    "sound": True},
    {"block": 1, "phase": "transition",  "condition": "AS+PS+NF", "sound": True},
    {"block": 1, "phase": "test",        "condition": "AS",       "sound": True},

    {"block": 2, "phase": "training",    "condition": "AS+PS",    "sound": True},
    {"block": 2, "phase": "transition",  "condition": "AS+PS+NF", "sound": True},
    {"block": 2, "phase": "test",        "condition": "PS",       "sound": False},

    #{"block": 3, "phase": "training",    "condition": "AS",       "sound": True},
    #{"block": 3, "phase": "test",        "condition": "AS",       "sound": True},

    #{"block": 4, "phase": "test",        "condition": "NO",       "sound": False},
]

randomized_design = []
for b in block_order:
    for row in design:
        if row["block"] == b:
            randomized_design.append(row)

# ==============================================================================
# MOUSE
# ==============================================================================
mouse = event.Mouse(win=win, visible=True)
try:
    mouse.useRaw = True
except Exception as e:
    print("Raw input not supported:", e)

# ==============================================================================
# VISUAL STIMULI
# ==============================================================================
target_x = 350
target_y = 0

target = visual.Circle(
    win,
    radius=8,
    pos=(target_x, target_y),
    fillColor='red',
    lineColor='red'
)
cursor = visual.Circle(win, radius=10, fillColor='white')

# ==============================================================================
# SOUNDS
# ==============================================================================
go_sound          = sound.Sound("short_sounds/beep-329314_ad.wav",  stereo=True)
happy_sound       = sound.Sound("short_sounds/complete_sound_ad.wav", stereo=True)
error_sound_over  = sound.Sound("short_sounds/error_over.wav",       stereo=True)
error_sound_under = sound.Sound("short_sounds/error_under.wav",      stereo=True)

# ==============================================================================
# TRIAL FUNCTION
# ==============================================================================
def run_trial(win, mouse, target_x, sound_files, phase, play_sounds, trial_num):

    # --- Ready screen ---
    ready_text = visual.TextStim(
        win,
        text="Adjust mouse to start position.\n\nPress z when ready.",
        color="white",
        height=28
    )
    ready_text.draw()
    win.flip()
    wait_keys_safe(keyList=["z", "escape"])

    mouse.setPos((-350, 0))
    clock = core.Clock()

    x_data, y_data, t_data = [], [], []

    offset_no = random.randint(1, 5)

    # --- Start screen (experimenter presses 'm') ---
    ready_text = visual.TextStim(
        win,
        text=(
            f"Trial {trial_num}\n\n"
            f"Move mouse physically to position {offset_no}.\n\n"
            "Press m key when ready."
        ),
        color="white",
        height=28
    )
    ready_text.draw()
    win.flip()
    wait_keys_safe(keyList=["m", "escape"])

    # -- Go sound + EEG trigger --
    go_sound.play()
    trigger(TRIG_GO_SOUND)   # sent immediately after play(); sub-frame precision

    # Distance from mouse start to target
    start_x, start_y = mouse.getPos()
    start_dist = ((start_x - target_x)**2 + (start_y - target_y)**2)**0.5

    # Build sound triggers
    triggers = []
    if play_sounds:
        for dist, filename, vol in sound_files:
            snd = sound.Sound(filename, volume=vol)
            if phase == "training":
                trig_code = TRIG_SOUND_TRAINING.get(dist, 99)
            elif phase == "transition":
                trig_code = TRIG_SOUND_TRANSITION.get(dist, 99)
            elif phase == "test":
                trig_code = TRIG_SOUND_TEST.get(dist, 99)
            else:
                trig_code = 99  # fallback if phase does not exist

            triggers.append({
                'distance':  dist,
                'sound':     snd,
                'trig_code': trig_code,
                'played':    False
            })

        # Skip triggers already behind the start position
        for t in triggers:
            if start_dist <= t['distance']:
                t['played'] = True

    manual_override = False
    escaped         = False

    # --- Trial loop ---
    while True:
        x, y = mouse.getPos()
        current_time = clock.getTime()

        x_data.append(x)
        y_data.append(y)
        t_data.append(current_time)

        target.draw()
        cursor.pos = (x, y)
        cursor.draw()
        win.flip()

        current_dist = ((x - target_x)**2 + (y - target_y)**2)**0.5

        # Sound + EEG triggers
        if play_sounds:
            for t in triggers:
                if not t['played'] and current_dist <= t['distance']:
                    t['sound'].play()
                    trigger(t['trig_code'])
                    t['played'] = True  # each code is only sent once per trial

        keys = event.getKeys()
        if 'o' in keys:
            print("Manual override triggered.")
            manual_override = True
            break
        if 'escape' in keys:
            escaped = True
            break

    # --- Build partial/complete DataFrame ---
    df = pd.DataFrame({'time': t_data, 'x': x_data, 'y': y_data, 'offset_pos': offset_no})

    # --- Outcome ---
    if manual_override or escaped:
        final_x, final_y = mouse.getPos()
        error = ((final_x - target_x)**2 + (final_y - target_y)**2)**0.5
        hit = False
        if phase == "training" and not escaped:
            error_sound_under.play()
        # Return the partial data before raising so the caller can save it
        if escaped:
            return error, hit, df, True   # 4th value signals escape
        return error, hit, df, False

    final_x = x_data[-1]
    final_y = y_data[-1]
    error = ((final_x - target_x)**2 + (final_y - target_y)**2)**0.5
    hit = error <= 37

    # Feedback sound (training only)
    if phase == "training":
        if hit:
            happy_sound.play()
        else:
            if final_x >= target_x:
                error_sound_over.play()
            else:
                error_sound_under.play()

    return error, hit, df, False


# ==============================================================================
# BLOCK RUNNERS
# ==============================================================================
def _save_trial(df, sub_id, block_num, phase, trial_num, condition):
    df['ID']         = sub_id
    df['block']      = block_num
    df['phase']      = phase
    df['trial']      = trial_num
    df['targ_x']     = 350
    df['targ_y']     = 0
    df['frame_rate'] = '60'
    df['order']      = str(block_order)
    df['condition']  = condition
    all_trials_data.append(df)


def run_training_block(n_trials, win, mouse, target_x, sound_files,
                       block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, escaped = run_trial(
            win=win, mouse=mouse, target_x=target_x,
            sound_files=sound_files, phase="training",
            play_sounds=play_sounds, trial_num=trial + 1
        )
        _save_trial(df, sub_id, block_num, "training", trial + 1, condition)
        if escaped:
            raise EscapePressed()
        show_feedback(win, error, hit)


def run_transition_block(n_trials, win, mouse, target_x, sound_files,
                         block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, escaped = run_trial(
            win=win, mouse=mouse, target_x=target_x,
            sound_files=sound_files, phase="transition",
            play_sounds=play_sounds, trial_num=trial + 1
        )
        _save_trial(df, sub_id, block_num, "transition", trial + 1, condition)
        if escaped:
            raise EscapePressed()


def run_test_block(n_trials, win, mouse, target_x, sound_files,
                   block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, escaped = run_trial(
            win=win, mouse=mouse, target_x=target_x,
            sound_files=sound_files, phase="test",
            play_sounds=play_sounds, trial_num=trial + 1
        )
        _save_trial(df, sub_id, block_num, "test", trial + 1, condition)
        if escaped:
            raise EscapePressed()


# ==============================================================================
# FEEDBACK + TEXT HELPERS
# ==============================================================================
def show_feedback(win, error, hit):
    txt = "Hit!" if hit else f"Missed by {error:.1f}px"
    col = "green" if hit else "red"
    message = visual.TextStim(win, text=txt, color=col, height=40)
    message.draw()
    win.flip()
    core.wait(1.5)


def show_text(win, message):
    """Shows a text screen and waits for any key. Raises EscapePressed on escape."""
    text_stim = visual.TextStim(win, text=message, color="white", height=30, wrapWidth=1000)
    text_stim.draw()
    win.flip()
    wait_keys_safe()   # raises EscapePressed if escape is pressed


# ==============================================================================
# MAIN EXPERIMENT LOOP
# ==============================================================================
training_trials   = 30
transition_trials = 6
test_trials       = 15

sound_triggers = [
    (605, 'short_sounds/short-swoosh.wav',   0.04),
    (525, 'short_sounds/slide.mp3',          0.5),
    (375, 'short_sounds/short-swoosh.wav',   0.07),
    (300, 'short_sounds/thud.mp3',           0.5),
    (210, 'short_sounds/match.mp3',          0.2),
    (145, 'short_sounds/thud.mp3',           0.4),
    ( 40, 'short_sounds/slide_target.wav',   0.2),
]

try:
    for row in randomized_design:
        block     = row["block"]
        phase     = row["phase"]
        condition = row["condition"]
        sound_on  = row["sound"]

        show_text(win, f"Block {block}\n\nPhase: {phase}\n\nCondition: {condition}\n\nPress any key to continue.")

        if phase == "training":
            show_text(win,
                "Training phase\n\n"
                "Feedback after each trial.\n\n"
                "Press any key to start training."
            )
            run_training_block(
                n_trials=training_trials, win=win, mouse=mouse,
                target_x=350, sound_files=sound_triggers,
                block_num=block, condition=condition, play_sounds=sound_on
            )

        elif phase == "transition":
            show_text(win,
                "Transition phase\n\n"
                "No feedback after each trial.\n\n"
                "Press any key to start transition."
            )
            run_transition_block(
                n_trials=transition_trials, win=win, mouse=mouse,
                target_x=350, sound_files=sound_triggers,
                block_num=block, condition=condition, play_sounds=sound_on
            )

        elif phase == "test":
            show_text(win,
                "Test phase\n\n"
                "No feedback will be provided.\n\n"
                "Press any key to start the test."
            )
            run_test_block(
                n_trials=test_trials, win=win, mouse=mouse,
                target_x=350, sound_files=sound_triggers,
                block_num=block, condition=condition, play_sounds=sound_on
            )

except EscapePressed:
    print("[main] Escape Pressed. Saving data and quitting.")
    safe_quit(reason="escape")

# ==============================================================================
# SAVE DATA  (reached only on normal completion)
# ==============================================================================
full_df = pd.concat(all_trials_data, ignore_index=True)
print(full_df.head())
print("Number of rows:", len(full_df))
print("Current working directory:", os.getcwd())

save_path = "data/"
os.makedirs(save_path, exist_ok=True)
filename = save_path + f"mouse_tracking_{sub_id}.csv"
full_df.to_csv(filename, index=False)
print(f"Saved all data to {filename}")

# Close port
if port_type == 'serial' and port is not None:
    port.close()

win.close()
core.quit()