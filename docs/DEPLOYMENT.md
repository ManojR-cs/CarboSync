# Deployment notes

The repository contains no Render manifest, build configuration, or evidence about a currently attached Render disk. The historical paths `/var/data/carbosync.db` and `/var/data/yolo11x.pt` only work if the service is configured with a writable persistent disk mounted at `/var/data` and the weights are actually present there. Neither condition can be verified from this source checkout. No live deployment or inference has been verified as part of the repository changes.

## Render configuration if deployment is retained

Before expecting persistent data or inference:

1. In Render service settings, inspect whether a persistent disk is attached and record its actual mount path. If present and writable, set `CARBOSYNC_DATABASE_PATH` to a file under that mount, for example `/var/data/carbosync.db`. Use a single service instance/worker with SQLite; otherwise use a managed database.
2. For detector inference, install `requirements-yolo.txt` in the deployment build and provision a compatible Ultralytics `.pt` file in the image or on durable storage. Set `CARBOSYNC_YOLO_MODEL_PATH` to its real path. Do not rely on an ephemeral instance filesystem or implicit server-start downloads. Health reports missing weights as `unavailable`; incompatibility/initialization errors report `failed`.
3. Configure `CARBOSYNC_YOLO_DEVICE=cpu` unless a supported GPU is actually available. The default live-demo model choice is YOLO11n; YOLO11x is not selected or downloaded by default.
4. Set `CARBOSYNC_CORS_ORIGINS` to exact trusted web origins. `CARBOSYNC_SERVE_FRONTEND=1` serves the checked-in static frontend from the API process when that is the intended layout.
5. Verify health and real inference against an appropriate test image after deployment. A healthy API response alone does not confirm detector readiness.

## Public data and security limitations

The API currently has unauthenticated student-record routes that can return names, IDs, and residential addresses. It also accepts writes and image uploads. Do not expose this application publicly or submit real student data until authorization, data minimization, retention, upload controls, and operational policies are implemented and reviewed. CORS is not an access-control system. Emission factors and results remain illustrative/unapproved.

Pushing to the repository may trigger an external deployment depending on GitHub/Render settings. This repository contains no integration settings that establish whether auto-deploy is enabled. Inspect the Render dashboard before relying on deployment behavior. No deployment will be manually triggered by these code changes.
