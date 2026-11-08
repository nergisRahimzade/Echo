# Echo: 3-minute demo script

**Before you start:** open `https://<api>.onrender.com/health` (it wakes the free server), then
run `python -m scripts.rehearse_demo --api https://<api>.onrender.com`, which should pass twice.
Open the website on the phone, tap **Try the demo account** (Deniz), and set Settings > Echo's voice.

## 1. Problem (30 s)
People with dysarthria (after a stroke, or with ALS or Parkinson's) know exactly what they want to say,
but strangers can't understand them. General speech recognition fails on their voice. Echo learns *their* voice.

## 2. Live demo (2 min)
1. **Turkish:** tap the button, say "Bugün kendimi daha iyi hissediyorum.", then tap it again. Echo says it clearly.
2. **English:** say "Can you call Zeynep for me?" The same session handles the other language.
3. **A check:** mumble "Biraz dinlenmek istiyorum." The score is under 0.80, so Echo plays it back
   privately. Tap 👍 and Echo says it to the listener.
4. **A correction that sticks:** say an unclear sentence, tap 👎 twice, and a helper types what was meant.
   Say it again: this time Echo gets it right, because it learned from the helper's correction.
5. Show the ring: "31 sentences learned". Open Names and places: Zeynep, Boncuk, Kadıköy.

## 3. Vision (30 s)
Every 👍 makes Echo better for this one person. It speaks Turkish and English today, and adding a language
takes one phrase list, one UI file and a voice. Next: the user's own voice, and a caregiver view.

## Backup
If the Wi-Fi fails, play the backup video, a screen recording of steps 1–5 (record it on a phone after the
rehearsal passes).
