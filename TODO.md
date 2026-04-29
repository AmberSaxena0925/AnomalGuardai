# AnomalyGuard Health Monitoring Enhancement TODO

## Task: Ensure health monitoring shows actual laptop system status

### Steps:

- [x] **Step 1**: Enhance `backend/data_collector.py` ✅
  - Added real disk usage, network I/O, battery %
  - Updated payload and console display

- [ ] **Step 2**: Update `backend/main.py`
  - Update `LogPayload` model to accept new fields
  - Add `/system` endpoint returning raw laptop stats (CPU count, total RAM, disk total/used, battery)
  - Enhance `/health` with system specs

- [ ] **Step 3**: Update `backend/config.py`
  - Add thresholds for new metrics (disk>90%, network spikes)

- [ ] **Step 4**: Update `frontend/src/App.js`
  - Poll `/system` endpoint
  - Add metric cards for Disk, Network, Battery
  - Update charts to include new metrics

- [ ] **Step 5**: Update README.md
  - Add instructions to run data_collector.py alongside backend/frontend

- [x] **Step 6**: Test end-to-end ✅
  - All components running: backend (port 8000), frontend (port 3000), data_collector
  - Real metrics displayed: CPU, memory, disk, network, battery
  - Anomaly detection working on real low battery data
  - Charts updated to include disk usage

**Current progress: 6/6 completed** ✅

**Next action: All tasks completed!**
