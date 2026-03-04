# Windows-Steam-Wrapper-for-MacOS


# shows enviornment info
python3 mysteamwine.py --wine /opt/local/bin/wine info
# creates wine bottle
python3 mysteamwine.py --wine /opt/local/bin/wine init 
# downloads steam
python3 mysteamwine.py --wine /opt/local/bin/wine install-steam
# opens steam
python3 mysteamwine.py --wine /opt/local/bin/wine run-steam

# TODO: Set up Winetricks