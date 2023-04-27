#!/bin/sh

# Clear screen
# echo -e "\033[2J"
clear

TERMINAL_WALLPAPER=/home/io/Projects/textual-paint/samples/galaxies.ans
# Draw terminal background (basic)
# cat $TERMINAL_WALLPAPER

# Split lines of terminal background into array
IFS=$'\n' read -d '' -r -a lines < $TERMINAL_WALLPAPER

# # Strips ANSI codes from text
# # 1: The text
# # >: The ANSI stripped text
# function strip_ansi() {
#   shopt -s extglob # function uses extended globbing
#   printf %s "${1//$'\e'\[*([0-9;])m/}"
# }

# Measure image size
image_height=${#lines[@]}
image_width=0
for (( y=0; y<$image_height; y++ )); do
	line=${lines[$y]}
	# Have to strip ANSI escape sequences from line length
	# line_width=50
	line_length=${#line}
	# line_width=$(echo $line | sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]//g" | wc -c)
	filtered_line=$(sed -r "s/\x1B\[[0-9;]*[mK]//g" <<< "$line")
	# line_width=$(echo "$filtered_line" | wc -c)
	# line_width=$(strip_ansi "$line" | wc -c)
	line_width=${#filtered_line}

	# echo "y=$y line         : $line line_length=$line_length line_width=$line_width"
	# echo "y=$y filtered line: $filtered_line"

	# echo "stripped: $(strip_ansi "$line") $(strip_ansi "$line" | wc -c)"
	if [[ $line_width -gt $image_width ]]; then
		image_width=$line_width
	fi
done
# echo "image_width: $image_width"
# echo "image_height: $image_height"
# Draw background centered
terminal_width=$(tput cols)
terminal_height=$(tput lines)
offset_x=$(( ($terminal_width - $image_width) / 2 ))
offset_y=$(( ($terminal_height - $image_height) / 2 ))
# echo "terminal_width: $terminal_width terminal_height: $terminal_height offset_x: $offset_x offset_y: $offset_y"
# ensure offset is positive
if [[ $offset_x -lt 0 ]]; then
	offset_x=0
fi
if [[ $offset_y -lt 0 ]]; then
	offset_y=0
fi
for (( i=0; i<$image_height; i++ )); do
  
  tput cup $(( $offset_y + $i )) $offset_x
  echo -e "${lines[$i]}"
done

# Reset cursor position
echo -e "\033[0;0H"
