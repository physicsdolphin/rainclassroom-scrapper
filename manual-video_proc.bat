@echo off
setlocal enabledelayedexpansion

:: Set the input and output folders
set "input_folder=C:\Users\YLW-LAPTOP\Downloads\Video"
set "output_folder=C:\Users\YLW-LAPTOP\Downloads\video\Output"

:: Ensure the output folder exists
if not exist "%output_folder%" (
    mkdir "%output_folder%"
)

:: Change to the input folder
cd /d "%input_folder%"

:: Initialize variables
set "current_group="
set "concat_file="

:: Loop through all files with the .mp4 extension in the input folder
for %%F in (*.mp4) do (
    :: Extract the group prefix from the filename (e.g., 1 from 1-1.mp4)
    for /f "tokens=1 delims=-" %%G in ("%%F") do (
        set "group_prefix=%%G"

        :: Check if we're still in the same group
        if not "!group_prefix!"=="!current_group!" (
            :: If a previous group exists, process it
            if defined current_group (
                :: Run ffmpeg with CUDA on the current group
                ffmpeg -f concat -safe 0 -i "!concat_file!" ^
                    -c:v hevc_nvenc -cq 28 -surfaces 64 -bufsize 12800k -r 7.5 -rc-lookahead 63 ^
                    -c:a copy "%output_folder%\!current_group!_output.mp4" -n -hide_banner -loglevel warning -stats

                :: Clean up the temporary concat file
                del "!concat_file!"
            )

            :: Start a new group and reset concat file
            set "current_group=!group_prefix!"
            set "concat_file=%output_folder%\!current_group!_concat.txt"
            echo Creating concat file for group !current_group!

            :: Initialize the concat file for the new group
            > "!concat_file!" echo file '%input_folder%\%%F'
        ) else (
            :: Append the current file to the concat file
            >> "!concat_file!" echo file '%input_folder%\%%F'
        )
    )
)

:: Process the last group if needed
if defined current_group (
    ffmpeg -f concat -safe 0 -i "!concat_file!" ^
        -c:v hevc_nvenc -cq 28 -surfaces 64 -bufsize 12800k -r 7.5 -rc-lookahead 63 ^
        -c:a copy "%output_folder%\!current_group!_output.mp4" -n -hide_banner -loglevel warning -stats
    del "!concat_file!"
)

echo All videos processed!
endlocal
pause
