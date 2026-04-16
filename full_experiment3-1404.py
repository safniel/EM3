import psychopy
psychopy.useVersion('2023.1.3')
import pandas as pd
import os, random
from psychopy import sound, visual, core, event, gui
from collections import deque


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

    event.waitKeys(keyList = ["z"]) 
    
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

    event.waitKeys(keyList = ["m"])   # experimenter presses key to start trial
    go_sound.play()
    
    # Distance from mouse start to target
    start_x, start_y = mouse.getPos()
    start_dist = ((start_x - target_x)**2 + (start_y - target_y)**2)**0.5
    
    #prepare sound
    triggers = []
    if play_sounds:
        for dist, filename, vol in sound_files:
            snd = sound.Sound(filename, volume=vol)
            triggers.append({
                'distance': dist,     # distance from target at which sound fires
                'sound': snd,
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
    
    # Trial loop
    while True:
        x, y = mouse.getPos()
        current_time = clock.getTime()
        
        # store data
        x_data.append(x)
        y_data.append(y)
        t_data.append(current_time)
    
        # Draw everything
        target.draw()
        cursor.pos = (x, y)
        cursor.draw()
        win.flip()
        
        # movement detection
        #if abs(x - prev_x) > stationary_threshold or abs(y - prev_y) > stationary_threshold:
            #last_moving_time = current_time  # reset timer when mouse moves
        #prev_x, prev_y = x, y
        
        current_dist = ((x - target_x)**2 + (y - target_y)**2)**0.5
        
        #sound triggers
        if play_sounds:
            for t in triggers:
                # Only fire a sound trigger AFTER crossing start_x_after_m
                if not t['played'] and current_dist <= t['distance']:
                    t['sound'].play()
                    t['played'] = True
        
        #stopping conditions
        
        keys = event.getKeys()
        # experimenter override: force undershoot trial
        if 'o' in keys:      # choose any key you want, here "o" for override
            print("Manual override triggered.")
            manual_override = True
            break
        
        if 'escape' in event.getKeys():
            escape_pressed = True
            break   # exit the trial loop safely
            
    

    ## THIS WILL ALWAYS GIVE WRONG - ISSUE
    # if manual_override:
    #     final_x, final_y = mouse.getPos()
    #     error = ((final_x - target_x)**2 + (final_y - target_y)**2)**0.5
    #     hit = False
    #     if phase == "training":
    #         error_sound_under.play()
    #     df = pd.DataFrame({
    #         'time': t_data,
    #         'x': x_data,
    #         'y': y_data,
    #         'offset_pos': offset_no
    #     })
    #     return error, hit, df, stop
    
    # ---------- compute performance ----------
    #final_x = x_data[-1]
    #error = abs(final_x - target_x)
    #hit = error <= 20  # 20-pixel tolerance
    final_x = x_data[-1]
    final_y = y_data[-1]

    # Euclidean distance to target
    error = ((final_x - target_x)**2 + (final_y - target_y)**2)**0.5
    
    #passed_target = final_x >= target_x - 15
    hit = error <= 37   # keep or adjust tolerance

    stop = False

    if phase == "training":    # or whatever your variable is called
        if hit:
            happy_sound.play()
        else:
            if final_x >= target_x:
                error_sound_over.play()
            else: 
                error_sound_under.play()
        ## for behavioural
        history.append(hit)

        stop = len(history) == 2 and sum(history) >= 1

    
    df = pd.DataFrame({
        'time': t_data,
        'x': x_data,
        'y': y_data,
        'offset_pos': offset_no
    })
    
    return error, hit, df, stop
    


# TRAINING
def run_training_block(n_trials, win, mouse, target_x, sound_files, block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, stop = run_trial(
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
        df['order']= str(block_order)
    
        # append to global list
        all_trials_data.append(df)
        
        show_feedback(win, error, hit)
    
        if stop:
            print("Training criterion reached (7/10). Stopping early.")
            break

# TRANSITION
def run_transition_block(n_trials, win, mouse, target_x, sound_files, block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, stop = run_trial(
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
        df['order']= str(block_order)
    
        # append to global list
        all_trials_data.append(df)


# TEST
def run_test_block(n_trials, win, mouse, target_x, sound_files, block_num, condition, play_sounds):
    for trial in range(n_trials):
        error, hit, df, stop = run_trial(
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
        df['order']= str(block_order)

        all_trials_data.append(df)

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
        print("Trial:", trial, "| Condition:", condition, "| Sound:", play_sounds)
        error, hit, df, _ = run_trial(
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
        df['condition'] = condition      
        df['sound'] = play_sounds        
        df['targ_x'] = 350
        df['targ_y'] = 0
        df['frame_rate'] = '60'
        df['order'] = str(block_order)

        all_trials_data.append(df)


        
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
    text_stim = visual.TextStim(win, text=message, color="white", height=30, wrapWidth=1000)
    text_stim.draw()
    win.flip()
    event.waitKeys()  # waits for any key press
    


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

#mask_sound.stop()


# Combine all trial DataFrames into one
full_df = pd.concat(all_trials_data, ignore_index=True)

print(full_df.head())
print("Number of rows:", len(full_df))

print("Current working directory:", os.getcwd())

save_path = "data/"
os.makedirs(save_path, exist_ok=True)
filename = save_path + f"mouse_tracking_{sub_id}.csv"
full_df.to_csv(filename, index=False)

#filename = f"mouse_tracking_{sub_id}.csv"
#full_df.to_csv(filename, index=False)

print(f"Saved all data to {filename}")

win.close()
core.quit()

