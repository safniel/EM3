# INDSÆT I STARTEN:

import serial

# Define the port
port = serial.Serial("COM4", 115200)  # address for serial port is COM4 in this example. Change to match your machine.

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

# I RUN_TRIAL:

# Indsæt efter ready_text (specifikt efter følgende linje):
    # event.waitKeys(keyList=["m"]) 

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


 # --- Trial loop ---
    while True:
        x, y = mouse.getPos()
        current_time = clock.getTime()

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

# TIL SIDST:

# Luk port
port.close()

win.close()
core.quit()