#!/bin/bash

# Clear screen
tput clear

# Check environment variables
init_script="$HOME/.bashrc"
if [[ -f $HOME/.zshrc ]]; then
	init_script="$HOME/.zshrc"
fi
# uninstall_instruction="uninstall terminal wallpaper support with 'textual-paint --remove-wallpaper'"
this_script_abs_path=${BASH_SOURCE[0]}
# Note to self: DRY isn't worth it for outputting English instructions
source_line="source $this_script_abs_path"
uninstall_instruction="uninstall terminal wallpaper support by removing \"$source_line\" from $init_script"
add_var_instruction="Add it to $init_script before the line that includes terminal-wallpaper.sh (\"$source_line\"), or $uninstall_instruction"
if [[ -z $TERMINAL_WALLPAPER ]]; then
	echo "TERMINAL_WALLPAPER not set. $add_var_instruction"
	return
fi
if [[ -z $TERMINAL_WALLPAPER_MODE ]]; then
	echo "TERMINAL_WALLPAPER_MODE not set. $add_var_instruction"
	return
fi
# Check file exists
if [[ ! -f $TERMINAL_WALLPAPER ]]; then
	echo "TERMINAL_WALLPAPER file not found: $TERMINAL_WALLPAPER\nUpdate TERMINAL_WALLPAPER in $init_script, or $uninstall_instruction"
	return
fi

# Draw terminal background according to mode
if [[ $TERMINAL_WALLPAPER_MODE == "TOP_LEFT" ]]; then
	cat $TERMINAL_WALLPAPER
else
	# Split lines of terminal background into array
	IFS=$'\n' read -d '' -r -a lines < $TERMINAL_WALLPAPER

	# Measure image size
	image_height=${#lines[@]}
	image_width=0
	for (( y=0; y<$image_height; y++ )); do
		line=${lines[$y]}
		# Have to strip ANSI escape sequences from line length
		line_length=${#line}
		filtered_line=$(sed -r "s/\x1B\[[0-9;]*[mK]//g" <<< "$line")
		line_width=${#filtered_line}

		# echo "y=$y line         : $line line_length=$line_length"
		# echo "y=$y filtered line: $filtered_line line_width=$line_width"

		if [[ $line_width -gt $image_width ]]; then
			image_width=$line_width
		fi
	done

	if [[ $TERMINAL_WALLPAPER_MODE == "CENTER" ]]; then
		# Calculate offset
		terminal_width=$(tput cols)
		terminal_height=$(tput lines)
		offset_x=$(( ($terminal_width - $image_width) / 2 ))
		offset_y=$(( ($terminal_height - $image_height) / 2 ))
		# Ensure offset is positive
		if [[ $offset_x -lt 0 ]]; then offset_x=0; fi
		if [[ $offset_y -lt 0 ]]; then offset_y=0; fi
		# Draw image
		for (( i=0; i<$image_height; i++ )); do
			tput cup $(( $offset_y + $i )) $offset_x
			echo -e "${lines[$i]}"
		done
	elif [[ $TERMINAL_WALLPAPER_MODE == "TILE" ]]; then
		# Draw tiled image
		tput rmam
		setterm -linewrap off
		terminal_width=$(tput cols)
		terminal_height=$(tput lines)
		for (( y=0; y<$terminal_height; y+=$image_height )); do
			for (( x=0; x<$terminal_width; x+=$image_width )); do
				for (( i=0; i<$image_height; i++ )); do
					# Don't scroll past bottom of terminal
					if [[ $(( $y + $i + 1 )) -ge $terminal_height ]]; then
						break
					fi
					# Draw line
					tput cup $(( $y + $i )) $x
					echo -e "${lines[$i]}"
				done
			done
		done
		tput smam
		setterm -linewrap on
	fi
fi

# Reset cursor position
tput cup 0 0
