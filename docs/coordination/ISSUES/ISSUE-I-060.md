# I-060: Independent final regression

Status: Blocked by all required implementation issues  
Ownership: read-only

## Validation

```powershell
cd E:\Consultation_agent\backend
python -B -m compileall -q app
python -B -m pytest -p no:cacheprovider -q
python -B -m alembic -c alembic.ini heads

cd E:\Consultation_agent\frontend
npm run build

cd E:\Consultation_agent
docker compose config
docker compose --profile staging config
git diff --check
git status --short -uall
```

Unavailable checks are marked unverified. A failure creates a bounded repair issue;
this issue never performs opportunistic edits. No commit, deploy, live API, email,
or production database action is permitted.
