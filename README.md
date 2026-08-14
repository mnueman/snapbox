# photobooth

Code for Overtinker's portable photobooth.

## Button interface:

| Presses | Create Mode | Browse Mode |
| --- | --- | --- |
| 1 short | Take a photo (or save the strip + start a new one if it's full) | Next older strip |
| 2 short | Next frame design | Next newer strip |
| 3 short | Switch between 3-photo and 4-photo | Print two copies side by side |
| Long press (1s+) | Switch to browse | Switch to create |
| Super long press (6s+) | Shut down | Shut down |

## Useful commands

shutdown Pi safely:

`sudo shutdown -h now`

copy photobooth.py to Pi:

`scp photobooth.py username@photobooth.local:~/photobooth/`

copy frames and jsons to Pi:

`scp frames/* username@photobooth.local:~/photobooth/frames/`

debug photobooth service (it runs on boot):

`journalctl -u photobooth.service -f`

stop the photobooth service:

`sudo systemctl stop photobooth.service`

restart the photobooth service:

`sudo systemctl restart photobooth.service`
