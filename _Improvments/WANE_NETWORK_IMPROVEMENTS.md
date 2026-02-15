# Wane — Distributed Network Rendering Improvement Notes

> **Project:** Wane (Multi-Engine Render Queue Manager)
> **Repository:** https://github.com/sbuff25/RenderManager
> **Area:** Distributed / Network Rendering (Phase 2)
> **Architecture:** Server/Worker model with SQLite job queue, REST API, NiceGUI web UI

---

## Bug Fixes (Critical)

### BUG-01: Distributed Frame Completion Count Not Updating

**Status:** 🔴 Open
**Priority:** Critical
**Symptoms:** When a job renders distributively across multiple machines, the "frames completed" counter does not update correctly. The total completed frames across all workers are not being aggregated back to the server's job record.

**Expected Behavior:** The server should aggregate frame completion reports from ALL workers rendering a given job and display the combined total (e.g., if Worker A finishes 5 frames and Worker B finishes 3, the job should show 8 frames completed).

**Investigation Points:**
- Check how workers report frame completion back to the server (likely via `/api/jobs/{id}` or heartbeat endpoint)
- Verify the server-side handler that receives frame completion updates — it may be overwriting the count instead of incrementing it
- Check for race conditions where two workers report simultaneously and one update gets lost
- Review the database update query — should use atomic increment (`SET frames_completed = frames_completed + N`) rather than absolute set (`SET frames_completed = N`)
- Consider the existing "high water mark" fix for Vantage progress tracking — similar pattern may be needed at the distributed level

**Context:** A previous bug with Vantage single-machine rendering had a similar issue where frame counts would reset due to percentage-based vs frame-number interpretation mismatch. The fix used a "high water mark" to prevent regression. The distributed version may need an analogous approach where each worker tracks its own completed frames and the server sums across workers.

---

### BUG-02: Job Cancellation Does Not Propagate to All Workers

**Status:** 🔴 Open
**Priority:** Critical
**Symptoms:** When a job is killed/removed from the queue on the server, one worker stops rendering but the other machine continues rendering even after the job has been removed from the queue.

**Expected Behavior:** Cancelling or removing a job on the server must immediately signal ALL workers currently rendering that job to stop. No orphaned renders should persist.

**Investigation Points:**
- Check the job cancellation flow — does the server notify workers, or do workers only learn about cancellation on their next heartbeat/poll?
- Workers likely poll for their next job or send heartbeats — during these cycles, they should check if their current job is still active
- The worker's `cancel_render()` method exists and works (confirmed for Vantage with Abort button click, Blender via process kill) — the issue is the signal never reaches the second worker
- Consider adding a cancellation check in the worker's render loop (e.g., between frames, poll the server for job status)
- Consider WebSocket push notification for immediate cancellation rather than relying on polling intervals
- Review the `WainWorker.stop()` method — it calls `self.current_engine.cancel_render()` but this may only trigger on local `KeyboardInterrupt`, not on remote cancellation signals

**Suggested Fix Approach:**
1. Add a `/api/jobs/{id}/status` check in the worker render loop (between frames)
2. If job status is `cancelled` or job no longer exists, call `self.current_engine.cancel_render()`
3. Optionally: server pushes cancel event via WebSocket for faster response
4. Ensure ALL workers rendering chunks of the same job receive the cancellation

---

## Feature Requests

### FEAT-01: Dynamic Frame Redistribution (Load Balancing)

**Status:** 🟡 Planned
**Priority:** High
**Description:** When a job's frames are distributed across multiple workers and one worker finishes its allotted frames before the other(s), Wane should automatically redistribute remaining unrendered frames to the idle worker.

**Expected Behavior:**
1. Job with frames 1–100 is split: Worker A gets 1–50, Worker B gets 51–100
2. Worker A finishes frames 1–50 while Worker B is only at frame 70
3. Wane automatically assigns frames 85–100 (or a portion of remaining) to Worker A
4. Both workers continue rendering until all frames are complete

**Implementation Considerations:**
- Frame assignments should be tracked at a granular level in the database (which frames are assigned to which worker, which are completed, which are pending)
- When a worker completes its assigned chunk, it should request more work from the server (`/api/workers/{id}/next-job` or a new `/api/workers/{id}/next-frames` endpoint)
- The server should be able to reclaim unstarted frames from a slow worker's assignment and reassign them
- Avoid reassigning a frame that is currently mid-render on another machine — only reassign frames that haven't started yet
- Consider a chunk-based approach: instead of assigning all frames upfront, assign small chunks (e.g., 5–10 frames) and let workers request new chunks as they finish
- This chunk-based approach also naturally solves the load balancing problem — faster machines simply complete more chunks

**Database Schema Consideration:**
```
frame_assignments table:
  - job_id
  - frame_number
  - worker_id (nullable — unassigned if NULL)
  - status (pending / rendering / completed / failed)
  - assigned_at
  - completed_at
```

**Hardware Safety Note:** Frame redistribution should respect GPU temperature limits. If a worker's GPU is running hot, it should not receive additional frames. Integrate with existing GPU temperature monitoring and auto-pause functionality.

---

## Summary — Task Priority Order

| Priority | ID | Type | Description |
|----------|----|------|-------------|
| 1 | BUG-02 | Bug | Job cancellation must propagate to ALL workers |
| 2 | BUG-01 | Bug | Fix distributed frame completion counting |
| 3 | FEAT-01 | Feature | Dynamic frame redistribution / load balancing |

---

*Last updated: 2026-02-14*
*Add new notes below this line as development continues.*
