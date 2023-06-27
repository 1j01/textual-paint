"""
Implements the Recent File Storage Specification

https://specifications.freedesktop.org/recent-file-spec/recent-file-spec-0.2.html

TODO: use the Registry on Windows
"""

import os
import time
import fcntl
import xml.etree.ElementTree as ET

RECENT_FILE_PATH = os.path.expanduser("~/.recently-used")
MAX_RECENT_FILES = 500


def add_recent_file(uri, mime_type, groups=None):
    # Load recent files
    recent_files = load_recent_files()

    # Check if the file already exists in the recent files
    existing_item = find_recent_file_by_uri(recent_files, uri)
    if existing_item:
        existing_item.find("Timestamp").text = str(int(time.time()))
        if groups:
            groups_elem = existing_item.find("Groups")
            for group in groups:
                group_elem = ET.SubElement(groups_elem, "Group")
                group_elem.text = group
    else:
        # Create new recent item
        recent_item = ET.Element("RecentItem")
        ET.SubElement(recent_item, "URI").text = uri
        ET.SubElement(recent_item, "Mime-Type").text = mime_type
        ET.SubElement(recent_item, "Timestamp").text = str(int(time.time()))

        if groups:
            groups_elem = ET.SubElement(recent_item, "Groups")
            for group in groups:
                group_elem = ET.SubElement(groups_elem, "Group")
                group_elem.text = group

        # Add the new recent item to the list
        recent_files.append(recent_item)

    # Truncate the recent files list if necessary
    if len(recent_files) > MAX_RECENT_FILES:
        recent_files = recent_files[-MAX_RECENT_FILES:]

    # Save the recent files
    save_recent_files(recent_files)


def get_recent_files():
    # Load and return the recent files
    return load_recent_files()


def load_recent_files():
    # Create an empty recent files list
    recent_files = []

    # Lock the recent file for reading
    with open(RECENT_FILE_PATH, "a+") as file:
        try:
            # Try to read the file content
            file.seek(0)
            fcntl.lockf(file, fcntl.LOCK_SH)
            content = file.read()

            if content:
                # Parse the XML document
                root = ET.fromstring(content)
                recent_files = root.findall("RecentItem")
        except (ET.ParseError, FileNotFoundError):
            # Handle file not found or invalid XML format
            pass
        finally:
            # Unlock the recent file after reading
            fcntl.lockf(file, fcntl.LOCK_UN)

    return recent_files


def save_recent_files(recent_files):
    # Lock the recent file for writing
    with open(RECENT_FILE_PATH, "r+") as file:
        try:
            fcntl.lockf(file, fcntl.LOCK_EX)
            # Try to read the existing content
            content = file.read()
            file.seek(0)

            if content:
                # Parse the XML document
                root = ET.fromstring(content)
                existing_items = root.findall("RecentItem")

                # Remove existing items from the root element
                for item in existing_items:
                    root.remove(item)

            else:
                # Create the root element if the file is empty
                root = ET.Element("RecentFiles")

            # Add each recent item to the root element
            for item in recent_files:
                root.append(item)

            # Serialize the XML document
            xml_data = ET.tostring(root, encoding="utf-8")

            # Write the XML document to the file
            file.write(xml_data.decode())
            file.truncate()
        finally:
            # Unlock the recent file after writing
            fcntl.lockf(file, fcntl.LOCK_UN)


def find_recent_file_by_uri(recent_files, uri):
    for item in recent_files:
        uri_elem = item.find("URI")
        if uri_elem is not None and uri_elem.text == uri:
            return item
    return None
