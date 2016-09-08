# thebarebox_printing_server

Script runs on boot via Windows Scheduled Tasks.   

To restart the printing script in case of trouble shooting or error:

-Remote Desktop into the PC Stick if no peripherals are attached
-Upon viewing the desktop- continue with below
-First, close the black printing window (COMMAND utility) or stop the service by placing the cursor in the window and hit ESC or CTRL + C to quit the running program 
-Troubleshoot as needed- there might possibly an error readout in the black window...save this error message as it could contain important information.  Otherwise, check the printing cue or printing device to see if any error messages have surfaced.
-To restart the printing script, either or restart the PC stick or make sure the cursor is in the COMMAND window, type “cd Desktop/printing_server” and press ENTER.   Then type “python client.py” and press ENTER.  The script should be running now.   

