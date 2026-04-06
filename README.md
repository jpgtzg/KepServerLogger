# Dev notes

The KepServer driver for the channel 'KepServerLogger' from which all data is sent/received from, is a Simulator. This allows for using an OPC UA Channel without a having a physical device.

KepServer tags doesn't allow the use of dots in the tag name. Thefore, with the actual tag name, the dots are replace with underscores. For example, if the tag name (no prefix) is 'KEPServerEX 6.18 Config API Service_0, the tag name in OPC UA is 'KEPServerEX 6_18 Config API Service_0'. 