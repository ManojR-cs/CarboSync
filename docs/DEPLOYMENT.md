# Deployment readiness

The repository currently supports a local demo. The backend is **not safe to expose publicly** as-is:

- There is no authentication or authorization.
- `/api/demo/students` returns student names, IDs, and residential addresses, and the write endpoint accepts those records.
- CORS does not protect these routes from direct HTTP callers.
- There is no application-level rate limiting for uploads or writes.
- SQLite persistence and detector weights are local/manual; a hosting environment needs durable storage and a controlled model-provisioning path.
- Emission factors are illustrative or unapproved, and campus-image detection accuracy is not established.

Do not deploy the current full API to a public URL or enter real student data. No external deployment has been created.

## Required before public hosting

1. Remove the student-record workflow or add reviewed authentication, authorization, and data minimization. Confirm that no public route can return names, identifiers, or home addresses.
2. Add request throttling and review file-upload limits, retention, and access policies.
3. Decide whether this is a synthetic-only judging demo or a real-data product. For a public judging demo, seed synthetic records and disable all real student-data reads/writes.
4. Choose a host, region, and durable database/model storage. SQLite on a local persistent disk requires a single service instance and worker; otherwise migrate to a managed database.
5. Provision and verify the exact detector weights securely if real inference is part of the demo. Without that, keep inference explicitly unavailable or simulated and labelled.
6. Set production CORS to exact trusted HTTPS origins, run the tests and smoke tests against the deployment, and verify health, data persistence, and error behavior.

After the public-data boundary is fixed, deployment needs the chosen hosting account/project and permission to connect this GitHub repository. Do not send provider secrets in chat or commit them; enter them in the host's secret manager.
