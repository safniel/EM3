import psychopy
psychopy.useVersion('2023.1.3')
import pandas as pd
import os, random
from psychopy import sound, visual, core, event, gui
from collections import deque
import serial

# ### EEG ###
# # Try serial port first, then parallel port, then fall back to print-only.
# # Change "COM4" and 0x0378 to match your lab setup.
# try:
#     port = serial.Serial("COM4", 115200)
#     port_type = 'serial'
# except Exception:
#     try:
#         from psychopy import parallel
#         port = parallel.ParallelPort(0x0378)
#         port_type = 'parallel'
#     except Exception:
#         port = None
#         port_type = 'none'

# print(f'EEG port type: {port_type}')

# def trigger(code):
#     """Send an EEG trigger code and immediately reset to 0."""
#     if port_type == 'serial':
#         port.write(code.to_bytes(1, 'big'))
#     elif port_type == 'parallel':
#         port.setData(code)
#         core.wait(0.020)   # 20 ms pulse width
#         port.setData(0)
#     print(f'Trigger sent: {code}')
port = serial.Serial("COM3", 115200)  # address for serial port is COM4 in this example. Change to match your machine.

def trigger(code):
    port.write(code.to_bytes(1, 'big'))
    print('trigger sent {}'.format(code))

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



# ID
ID_box = gui.Dlg(title = 'Subject identity')
ID_box.addField('ID: ', '')
ID_box.addField(
    'Block order:',
    choices=[
        '1-2-3',
        '1-3-2',
        '2-1-3',
        '2-3-1',
        '3-1-2',
        '3-2-1',
        '1',
        '2',
        '3',
        '5'
    ]
)
ok = ID_box.show()
sub_id = ok[0]
order_str = ok[1]
block_order = list(map(int, order_str.split('-')))


# SCREEN SETUP
# Setup the experiment window
win = visual.Window(
    fullscr=True,
    color="black",
    units='pix'  # use pixel units for direct mapping
)



all_trials_data = []   # stores data from ALL training + test trials


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


# -----------------------------
#  BLOCK / PHASE DESIGN TABLE
# -----------------------------
design = [
    {"block": 1, "phase": "training", "condition": "AS+PS", "sound": True},
    {"block": 1, "phase": "transition", "condition": "AS+PS", "sound": True},
    {"block": 1, "phase": "test",     "condition": "AS",    "sound": True},

    {"block": 2, "phase": "training", "condition": "AS+PS", "sound": True},
    {"block": 2, "phase": "transition", "condition": "AS+PS", "sound": True},
    {"block": 2, "phase": "test",     "condition": "PS",    "sound": False},

    {"block": 3, "phase": "training", "condition": "AS",    "sound": True},
    {"block": 3, "phase": "test",     "condition": "AS",    "sound": True},
    
    {"block": 4, "phase": "test",     "condition": "NO",    "sound": False},

    {"block": 5, "phase": "transition", "condition": "AS+PS", "sound": True},
    {"block": 5, "phase": "test",     "condition": "MIX",   "sound": None},
]

# -----------------------------
# Build design in this order
# -----------------------------
randomized_design = []
for b in block_order:
    for row in design:
        if row["block"] == b:
            randomized_design.append(row)

# Mouse set-up
mouse = event.Mouse(win=win, visible=True)
#mouse.setSystemCursor('crosshair')   # optional
try:
    mouse.useRaw = True  # disable OS acceleration if supported
except Exception as e:
    print("Raw input not supported:", e)


# Visual stimuli
#target_x = 280  #pixels from centre
#target = visual.Rect(win, width=5, height=win.size[1], pos=(target_x, 0), fillColor='red', lineColor='red')
target_x = 350
target_y = 0

target = visual.Circle(
    win,
    radius=8,              # small point
    pos=(target_x, target_y),
    fillColor='red',
    lineColor='red'
)
cursor = visual.Circle(win, radius=10, fillColor='white')



#Ideally this should be loaded outside the trial, but they get quieter, this is for go_sound as well
go_sound = sound.Sound("short_sounds/beep-329314_ad.wav", stereo=True)

happy_sound = sound.Sound("short_sounds/complete_sound_ad.wav", stereo=True)
error_sound_over = sound.Sound("short_sounds/error_over.wav", stereo=True)
error_sound_under = sound.Sound("short_sounds/error_under.wav", stereo=True)


# TRIAL FUNCTION
def run_trial(win, mouse, target_x, sound_files, block, phase, condition, play_sounds, trial_num):
    #reset mouse
    ready_text = visual.TextStim(
                win,
                text=f"Condition: {condition}\n\nAdjust mouse to start position.\n\nPress z when ready.",
                color="white",
                height=28
    )
    ready_text.draw()
    win.flip()
    wait_keys_safe(keyList=["z", "escape"])

    mouse.setPos((-350, 0))
    #clock
    clock = core.Clock()
    
    # Data
    x_data, y_data, t_data = [], [], []
    
    offset_no = random.randint(1, 5) 
    
    #adjust for starting position
    ready_text = visual.TextStim(
            win,
            text=f"Trial {trial_num}\n\nMove mouse physically to postion {offset_no}.\n\n Press m key when ready.",
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
            else: trig_code = 99 # fallback if phase does not exist

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
    #====================================================#

    
    # Distance from mouse start to target
    start_x, start_y = mouse.getPos()
    start_dist = ((start_x - target_x)**2 + (start_y - target_y)**2)**0.5
    
    #prepare sound
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
                'distance': dist,
                'sound': snd,
                'trig_code': trig_code,
                'played': False
            })
            
        # Mark triggers that were already passed at the moment of pressing 'm' as played/skipped
        for t in triggers:
            # if trigger position is <= start_x_after_m, mark it skipped
            if start_dist <= t['distance']:
                t['played'] = True
    
    #max_time = 10  # seconds safety timeout

    #stationary_threshold = 1.0  # small movement counts as moving
    #stationary_time_needed = 2.0  # seconds to wait after stopping
    #last_moving_time = 0  # or last_moving_time = clock.getTime()
    
    #prev_x, prev_y = mouse.getPos()
    
    
    manual_override = False
    escaped         = False
    
    # Trial loop
    while True:
        x, y = mouse.getPos()
        current_time = clock.getTime()
        
        # store data
        x_data.append(x)
        y_data.append(y)
        t_data.append(current_time)   
       
        current_dist = ((x - target_x)**2 + (y - target_y)**2)**0.5
        
        # Sound + EEG triggers
        if play_sounds:
            for t in triggers:
                if not t['played'] and current_dist <= t['distance']:
                    # Schedule both sound and EEG trigger on the same flip
                    t['sound'].play()
                    win.callOnFlip(trigger, t['trig_code'])
                    t['played'] = True # each code is only sent once per tiral

        target.draw()
        cursor.pos = (x, y)
        cursor.draw()
        win.flip()
        
        #stopping conditions
        
        keys = event.getKeys()
        # experimenter override: force undershoot trial
        if 'o' in keys:      # choose any key you want, here "o" for override
            print("Manual override triggered.")
            manual_override = True
            break
        
        if 'escape' in keys:
            escaped = True
            break   # exit the trial loop safely
            
    

    ## outcome section
    final_x = x_data[-1]
    final_y = y_data[-1]

    # Euclidean distance to target
    error = ((final_x - target_x)**2 + (final_y - target_y)**2)**0.5

    hit = error <= 37   # keep or adjust tolerance

    # If escape was pressed, return partial data immediately without feedback
    if escaped:
        df = pd.DataFrame({
            'time': t_data,
            'x': x_data,
            'y': y_data,
            'offset_pos': offset_no
        })
        return error, hit, df, True   # True = escaped


    if phase == "training":
        if hit:
            happy_sound.play()
        else:
            if final_x >= target_x:
                error_sound_over.play()
            else: 
                error_sound_under.play()
        ## for behavioural
        history.append(hit)

    df = pd.DataFrame({
        'time': t_data,
        'x': x_data,
        'y': y_data,
        'offset_pos': offset_no
    })
    
    return error, hit, df, False   # False = not escaped
    


# TRAINING
def run_training_block(n_trials, win, mouse, target_x, sound_files, block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, escaped = run_trial(
                        win=win,
                        mouse=mouse,
                        target_x=target_x,
                        sound_files=sound_files,
                        block=block_num,
                        phase="training",
                        condition=condition,
                        play_sounds=play_sounds,
                        trial_num=trial + 1
                        )
        # add metadata columns to the trial data
        df['ID'] = sub_id
        df['block'] = block_num
        df['phase'] = 'training'
        df['trial'] = trial + 1
        df['targ_x'] = 350
        df['targ_y'] = 0
        df['frame_rate'] = '60'
        df['order'] = str(block_order)
        df['condition'] = condition
    
        # append to global list
        all_trials_data.append(df)

        if escaped:
            raise EscapePressed()

        show_feedback(win, error, hit)

        # # Early-stop criterion (checked via history updated inside run_trial)
        # if len(history) == 2 and sum(history) >= 1:
        #     print("Training criterion reached. Stopping early.")
        #     break

# TRANSITION
def run_transition_block(n_trials, win, mouse, target_x, sound_files, block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, escaped = run_trial(
                        win=win,
                        mouse=mouse,
                        target_x=target_x,
                        sound_files=sound_files,
                        block=block_num,
                        phase="transition",
                        condition=condition,
                        play_sounds=play_sounds,
                        trial_num=trial + 1
                        )
        # add metadata columns to the trial data
        df['ID'] = sub_id
        df['block'] = block_num
        df['phase'] = 'transition'
        df['trial'] = trial + 1
        df['targ_x'] = 350
        df['targ_y'] = 0
        df['frame_rate'] = '60'
        df['order'] = str(block_order)
        df['condition'] = condition
    
        # append to global list
        all_trials_data.append(df)

        if escaped:
            raise EscapePressed()


# TEST
def run_test_block(n_trials, win, mouse, target_x, sound_files, block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, escaped = run_trial(
                        win=win,
                        mouse=mouse,
                        target_x=target_x,
                        sound_files=sound_files,
                        block=block_num,
                        phase="test",
                        condition=condition,
                        play_sounds=play_sounds,
                        trial_num=trial + 1
                        )
        # no feedback
        
        df['ID'] = sub_id
        df['block'] = block_num
        df['phase'] = 'test'
        df['trial'] = trial + 1
        df['targ_x'] = 350
        df['targ_y'] = 0
        df['frame_rate'] = '60'
        df['order'] = str(block_order)
        df['condition'] = condition

        all_trials_data.append(df)

        if escaped:
            raise EscapePressed()

# MIX TEST

#There are 3 different conditions
#These need to be changed. 
#The difference is whether sound is played or not.
#sound needs to be played 2/3 times.
#there needs to be something which says where it is AS + PS, AS, TS for the experimenter.





def generate_mixed_conditions(n_trials):
    trials = []

    # exact counts
    n_sound = int(n_trials * (2/3))
    n_ps = n_trials - n_sound  # PS = no sound

    # split sound trials between AS+PS and AS
    n_asps = n_sound // 2
    n_as = n_sound - n_asps

    # build list
    trials += [("AS+PS", True)] * n_asps
    trials += [("AS", True)] * n_as
    trials += [("PS", False)] * n_ps

    random.shuffle(trials)
    return trials

def run_mix_test_block(n_trials, win, mouse, target_x, sound_files, block_num):
    print("RUNNING MIXED BLOCK")
    trial_conditions = generate_mixed_conditions(n_trials)

    for trial, (trial_condition, play_sounds) in enumerate(trial_conditions):
        print("Trial:", trial, "| Condition:", trial_condition, "| Sound:", play_sounds)
        error, hit, df, escaped = run_trial(
            win=win,
            mouse=mouse,
            target_x=target_x,
            sound_files=sound_files,
            block=block_num,
            phase="test",
            condition=trial_condition,
            play_sounds=play_sounds,
            trial_num=trial + 1
         )

        df['ID'] = sub_id
        df['block'] = block_num
        df['phase'] = 'test'
        df['trial'] = trial + 1
        df['condition'] = trial_condition
        df['sound'] = play_sounds
        df['targ_x'] = 350
        df['targ_y'] = 0
        df['frame_rate'] = '60'
        df['order'] = str(block_order)

        all_trials_data.append(df)

        if escaped:
            raise EscapePressed()

#FEEDBACK
def show_feedback(win, error, hit):
    if hit:
        txt = "Hit!"
        col = "green"
    else:
        txt = f"Missed by {error:.1f}px"
        col = "red"

    message = visual.TextStim(win, text=txt, color=col, height=40)
    message.draw()
    win.flip()
    core.wait(1.5)

# Text
def show_text(win, message):
    """Shows a text screen and waits for any key. Raises EscapePressed on escape."""
    text_stim = visual.TextStim(win, text=message, color="white", height=30, wrapWidth=1000)
    text_stim.draw()
    win.flip()
    wait_keys_safe()   # raises EscapePressed if escape is pressed
    


### MAIN EXPERIMENT LOOP ###
training_trials = 4   # changeable
test_trials = 5       # changeable
transition_trials = 2

### TRAIN TO BASELINE FOR BEHAVIOURAL ###
### Overall max is 50 training
#training_trials_total = 60   # changeable
history = deque(maxlen=4)

def update(hit):
    history.append(hit)
    return len(history) == 4 and sum(history) >= 2




# sound triggers
sound_triggers = [
    (605, 'short_sounds/short-swoosh.wav', 0.04),
    (525, 'short_sounds/slide.mp3', 0.5),
    (375, 'short_sounds/short-swoosh.wav', 0.07),
    (300, 'short_sounds/thud.mp3', 0.5),
    (210, 'short_sounds/match.mp3', 0.2),
    (145, 'short_sounds/thud.mp3', 0.4),
    (40, 'short_sounds/slide_target.wav', 0.2),
]

# Continuous masker sound -> doesn't do anything,, but other sound won't load if I remove...
#mask_sound = sound.Sound('tv-static.wav', secs=-1, volume=0.0)  # -1 = play until stopped
#mask_sound.play()

### MAIN EXPERIMENT LOOP ###
try:
    for row in randomized_design:
        
        block     = row["block"]
        phase     = row["phase"]
        condition = row["condition"]
        sound_on  = row["sound"]
        
        #block intro text
        show_text(win, f"Block {block}\n\nPhase: {phase} \n\n Condition: {condition}\n\nPress any key to continue.")

        if phase == "training":
            show_text(win, 
                "Training phase\n\n"
                "Feedback after each trial.\n\n"
                "Press any key to start training."
            )        
            
            run_training_block(
                n_trials=training_trials,
                win=win,
                mouse=mouse,
                target_x=350,
                sound_files=sound_triggers,
                block_num=block,
                condition=condition,
                play_sounds=sound_on
            )
        
        if phase == "transition":
            show_text(win, 
                "Transition phase\n\n"
                "No feedback after each trial.\n\n"
                "Press any key to start training."
            )        
            run_transition_block(
                    n_trials=transition_trials,
                    win=win,
                    mouse=mouse,
                    target_x=350,
                    sound_files=sound_triggers,
                    block_num=block,
                    condition=condition,
                    play_sounds=sound_on
                )
        

        elif phase == "test" and condition != "MIX":
            show_text(win,
                "Test phase\n\n"
                "No feedback will be provided.\n\n"
                "Press any key to start the test."
            )
            
            run_test_block(
                n_trials=test_trials,
                win=win,
                mouse=mouse,
                target_x=350,
                sound_files=sound_triggers,
                block_num=block,
                condition=condition,
                play_sounds=sound_on
            )
        
        if phase == "test" and condition == "MIX":
            show_text(win,
                "Test phase\n\n"
                "No feedback will be provided.\n\n"
                "Press any key to start the test."
            )

            run_mix_test_block(
                n_trials = test_trials, 
                win=win, 
                mouse=mouse, 
                target_x=350, 
                sound_files=sound_triggers, 
                block_num=block)

except EscapePressed:
    print("[main] Escape pressed. Saving data and quitting.")
    safe_quit(reason="escape")

#mask_sound.stop()


# Combine all trial DataFrames into one (reached only on normal completion)
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
    try:
        port.close()
    except Exception:
        pass

win.close()
core.quit()
