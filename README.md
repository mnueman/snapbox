# photobooth

Code for Overtinker's portable photobooth.

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
