# How to

First install MetavisionSDK on a Linux system (here Ubuntu 22)

RUN: 

`python3 recordFromEVK4.py -b custom_biases/unnar_settings.bias`

to use bias parameters from Unnar. Otherwise it uses default parameters.


`# Configuration parameters
RECORDING_TIME = 5  # seconds to record
WAITING_TIME = 5    # seconds to wait between recordings
FOLDER_SIZE_CHECK_INTERVAL = 1  # seconds`
`

How long to record, how much to wait between recordings then checking the size of the new recordings