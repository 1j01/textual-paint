import os
import sys
import subprocess
import re

# There are too many desktop environment names and programs,
# it would pollute the spellings list (unless I moved this file
# to a folder and made a separate dictionary).
# spell-checker:disable

def get_desktop_environment(self):
    # From https://stackoverflow.com/a/21213358/2624876
    # which takes from:
    # http://stackoverflow.com/questions/2035657/what-is-my-current-desktop-environment
    # and http://ubuntuforums.org/showthread.php?t=652320
    # and http://ubuntuforums.org/showthread.php?t=652320
    # and http://ubuntuforums.org/showthread.php?t=1139057
    if sys.platform in ["win32", "cygwin"]:
        return "windows"
    elif sys.platform == "darwin":
        return "mac"
    else: #Most likely either a POSIX system or something not much common
        desktop_session = os.environ.get("DESKTOP_SESSION")
        if desktop_session is not None: #easier to match if we doesn't have  to deal with caracter cases
            desktop_session = desktop_session.lower()
            if desktop_session in [
                "gnome","unity", "cinnamon", "mate", "xfce4", "lxde", "fluxbox", 
                "blackbox", "openbox", "icewm", "jwm", "afterstep","trinity", "kde"
            ]:
                return desktop_session
            ## Special cases ##
            # Canonical sets $DESKTOP_SESSION to Lubuntu rather than LXDE if using LXDE.
            # There is no guarantee that they will not do the same with the other desktop environments.
            elif "xfce" in desktop_session or desktop_session.startswith("xubuntu"):
                return "xfce4"
            elif desktop_session.startswith('ubuntustudio'):
                return 'kde'
            elif desktop_session.startswith('ubuntu'):
                return 'gnome'     
            elif desktop_session.startswith("lubuntu"):
                return "lxde" 
            elif desktop_session.startswith("kubuntu"): 
                return "kde" 
            elif desktop_session.startswith("razor"): # e.g. razorkwin
                return "razor-qt"
            elif desktop_session.startswith("wmaker"): # e.g. wmaker-common
                return "windowmaker"
        if os.environ.get('KDE_FULL_SESSION') == 'true':
            return "kde"
        elif os.environ.get('GNOME_DESKTOP_SESSION_ID'):
            if not "deprecated" in os.environ.get('GNOME_DESKTOP_SESSION_ID'):
                return "gnome2"
        #From http://ubuntuforums.org/showthread.php?t=652320
        elif self.is_running("xfce-mcs-manage"):
            return "xfce4"
        elif self.is_running("ksmserver"):
            return "kde"
    return "unknown"

def is_running(self, process):
    #From http://www.bloggerpolis.com/2011/05/how-to-check-if-a-process-is-running-using-python/
    # and http://richarddingwall.name/2009/06/18/windows-equivalents-of-ps-and-kill-commands/
    try: #Linux/Unix
        s = subprocess.Popen(["ps", "axw"],stdout=subprocess.PIPE)
    except: #Windows
        s = subprocess.Popen(["tasklist", "/v"],stdout=subprocess.PIPE)
    for x in s.stdout:
        if re.search(process, x):
            return True
    return False


def set_wallpaper(self, file_loc, first_run):
    # From https://stackoverflow.com/a/21213504/2624876
    # I have not personally tested any of this.
    # -----------------------------------------

    # Note: There are two common Linux desktop environments where
    # I have not been able to set the desktop background from
    # command line: KDE, Enlightenment
    desktop_env = self.get_desktop_environment()
    try:
        if desktop_env in ["gnome", "unity", "cinnamon"]:
            uri = "'file://%s'" % file_loc
            try:
                SCHEMA = "org.gnome.desktop.background"
                KEY = "picture-uri"
                gsettings = Gio.Settings.new(SCHEMA)
                gsettings.set_string(KEY, uri)
            except Exception:
                args = ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri]
                subprocess.Popen(args)
        elif desktop_env=="mate":
            try: # MATE >= 1.6
                # info from http://wiki.mate-desktop.org/docs:gsettings
                args = ["gsettings", "set", "org.mate.background", "picture-filename", "'%s'" % file_loc]
                subprocess.Popen(args)
            except Exception: # MATE < 1.6
                # From https://bugs.launchpad.net/variety/+bug/1033918
                args = ["mateconftool-2","-t","string","--set","/desktop/mate/background/picture_filename",'"%s"' %file_loc]
                subprocess.Popen(args)
        elif desktop_env=="gnome2": # Not tested
            # From https://bugs.launchpad.net/variety/+bug/1033918
            args = ["gconftool-2","-t","string","--set","/desktop/gnome/background/picture_filename", '"%s"' %file_loc]
            subprocess.Popen(args)
        ## KDE4 is difficult
        ## see http://blog.zx2c4.com/699 for a solution that might work
        elif desktop_env in ["kde3", "trinity"]:
            # From http://ubuntuforums.org/archive/index.php/t-803417.html
            args = 'dcop kdesktop KBackgroundIface setWallpaper 0 "%s" 6' % file_loc
            subprocess.Popen(args,shell=True)
        elif desktop_env=="xfce4":
            #From http://www.commandlinefu.com/commands/view/2055/change-wallpaper-for-xfce4-4.6.0
            if first_run:
                args0 = ["xfconf-query", "-c", "xfce4-desktop", "-p", "/backdrop/screen0/monitor0/image-path", "-s", file_loc]
                args1 = ["xfconf-query", "-c", "xfce4-desktop", "-p", "/backdrop/screen0/monitor0/image-style", "-s", "3"]
                args2 = ["xfconf-query", "-c", "xfce4-desktop", "-p", "/backdrop/screen0/monitor0/image-show", "-s", "true"]
                subprocess.Popen(args0)
                subprocess.Popen(args1)
                subprocess.Popen(args2)
            args = ["xfdesktop","--reload"]
            subprocess.Popen(args)
        elif desktop_env=="razor-qt": #TODO: implement reload of desktop when possible
            if first_run:
                desktop_conf = configparser.ConfigParser()
                # Development version
                desktop_conf_file = os.path.join(self.get_config_dir("razor"),"desktop.conf") 
                if os.path.isfile(desktop_conf_file):
                    config_option = r"screens\1\desktops\1\wallpaper"
                else:
                    desktop_conf_file = os.path.join(self.get_home_dir(),".razor/desktop.conf")
                    config_option = r"desktops\1\wallpaper"
                desktop_conf.read(os.path.join(desktop_conf_file))
                try:
                    if desktop_conf.has_option("razor",config_option): #only replacing a value
                        desktop_conf.set("razor",config_option,file_loc)
                        with codecs.open(desktop_conf_file, "w", encoding="utf-8", errors="replace") as f:
                            desktop_conf.write(f)
                except Exception:
                    pass
            else:
                #TODO: reload desktop when possible
                pass 
        elif desktop_env in ["fluxbox","jwm","openbox","afterstep"]:
            #http://fluxbox-wiki.org/index.php/Howto_set_the_background
            # used fbsetbg on jwm too since I am too lazy to edit the XML configuration 
            # now where fbsetbg does the job excellent anyway. 
            # and I have not figured out how else it can be set on Openbox and AfterSTep
            # but fbsetbg works excellent here too.
            try:
                args = ["fbsetbg", file_loc]
                subprocess.Popen(args)
            except Exception:
                sys.stderr.write("ERROR: Failed to set wallpaper with fbsetbg!\n")
                sys.stderr.write("Please make sre that You have fbsetbg installed.\n")
        elif desktop_env=="icewm":
            # command found at http://urukrama.wordpress.com/2007/12/05/desktop-backgrounds-in-window-managers/
            args = ["icewmbg", file_loc]
            subprocess.Popen(args)
        elif desktop_env=="blackbox":
            # command found at http://blackboxwm.sourceforge.net/BlackboxDocumentation/BlackboxBackground
            args = ["bsetbg", "-full", file_loc]
            subprocess.Popen(args)
        elif desktop_env=="lxde":
            args = "pcmanfm --set-wallpaper %s --wallpaper-mode=scaled" % file_loc
            subprocess.Popen(args,shell=True)
        elif desktop_env=="windowmaker":
            # From http://www.commandlinefu.com/commands/view/3857/set-wallpaper-on-windowmaker-in-one-line
            args = "wmsetbg -s -u %s" % file_loc
            subprocess.Popen(args,shell=True)
        ## NOT TESTED BELOW - don't want to mess things up ##
        # elif desktop_env=="enlightenment": # I have not been able to make it work on e17. On e16 it would have been something in this direction
        #     args = "enlightenment_remote -desktop-bg-add 0 0 0 0 %s" % file_loc
        #     subprocess.Popen(args,shell=True)
        elif desktop_env=="windows": #Not tested since I do not run this on Windows
            #From https://stackoverflow.com/questions/1977694/change-desktop-background
            import ctypes
            SPI_SETDESKWALLPAPER = 20
            ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, file_loc, 0)
        elif desktop_env=="mac": #Not tested since I do not have a mac
           #From https://stackoverflow.com/questions/431205/how-can-i-programatically-change-the-background-in-mac-os-x
           try:
               from appscript import app, mactypes
               app('Finder').desktop_picture.set(mactypes.File(file_loc))
           except ImportError:
               #import subprocess
               SCRIPT = f"""/usr/bin/osascript<<END
               tell application "Finder" to
               set desktop picture to POSIX file "{file_loc}"
               end tell
               END"""
               subprocess.Popen(SCRIPT, shell=True)
        else:
            if first_run: #don't spam the user with the same message over and over again
                sys.stderr.write("Warning: Failed to set wallpaper. Your desktop environment is not supported.")
                sys.stderr.write("You can try manually to set your wallpaper to %s" % file_loc)
            return False
        return True
    except Exception as e:
        sys.stderr.write("ERROR: Failed to set wallpaper. There might be a bug.\n" + repr(e))
        return False
# spell-checker:enable

def get_config_dir(self, app_name=APP_NAME):
    if "XDG_CONFIG_HOME" in os.environ:
        config_home = os.environ['XDG_CONFIG_HOME'] 
    elif "APPDATA" in os.environ: # On Windows
        config_home = os.environ['APPDATA'] 
    else:
        try:
            from xdg import BaseDirectory   
            config_home =  BaseDirectory.xdg_config_home
        except ImportError: # Most likely a Linux/Unix system anyway
            config_home =  os.path.join(self.get_home_dir(), ".config")
    config_dir = os.path.join(config_home,app_name)
    return config_dir

def get_home_dir(self):
    return os.path.expanduser("~")
