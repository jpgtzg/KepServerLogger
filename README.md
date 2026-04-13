# Dev notes

The KepServer driver for the channel 'KepServerLogger' from which all data is sent/received from, is a Simulator. This allows for using an OPC UA Channel without a having a physical device.

KepServer tags doesn't allow the use of dots in the tag name. Thefore, with the actual tag name, the dots are replace with underscores. For example, if the tag name (no prefix) is 'KEPServerEX 6.18 Config API Service_0, the tag name in OPC UA is 'KEPServerEX 6_18 Config API Service_0'.

It is important to ensure, as obvious, that all nodes are correctly configured in the KepServer. This includes the correct address: if two nodes have the same address, they will both share the same data

# To do / Bugs

- [ ] Extractor connection to KepServer fails after some time. The KepServer logs show that the connection is closed by the client, but it is not clear why. It could be a timeout issue, or a problem with the OPC UA client implementation in the extractor. Further investigation is needed to identify the root cause and fix the issue. On other codes, or previous versions, like the one in the main branch, the connection seems to be stable, so it is possible that the issue is related to recent changes in the code. It would be helpful to compare the current implementation with the previous one to see if there are any differences that could explain the connection issues.
- [X] Migrate from using prints to using a proper logging framework.
- [X] Investigate why there are 100 KepServer events being logged
- [ ] Open up Docker connection to timescaledb to access database from another machine within the same network
- [ ] PLC_Tags have to also be accesible to the server. the current setup has them in another server
- [X] It appears that data is not being written to the database.
- [X] I manually inserted data into cpu_usage, and it appeared. After restart, it was still there. However, when i logged off/on the machine, it was not there anymore -> 0 data still (as per last error)
