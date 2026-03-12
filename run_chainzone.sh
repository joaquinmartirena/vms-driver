#!/bin/bash
export VMS_PANEL_IP=192.168.8.49
export VMS_DEVICE_TYPE=chainzone
export VMS_COMMUNITY_READ=public
export VMS_COMMUNITY_WRITE=public
python tools/message_playground.py
