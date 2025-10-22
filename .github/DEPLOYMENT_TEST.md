# Deployment Test - Phase 0 Week 1

This file tests the CD deployment pipeline to Linode staging.

## Test Details

- **Date**: 2025-01-22
- **Linode IP**: 173.255.230.154
- **User**: mftbot
- **Purpose**: Verify GitHub Secrets integration works

## Expected Behavior

When this file is pushed to `main`:

1. ✅ CI workflow runs (quality gate)
2. ✅ CD workflow runs (deployment)
3. ✅ SSH connection uses `STAGING_SSH_KEY` secret
4. ✅ Deploys to `STAGING_HOST` (173.255.230.154)
5. ✅ Files copied to `/home/mftbot/mft-trading-bot/`

## Verification

After deployment completes, SSH into Linode:

```bash
ssh mftbot@173.255.230.154
ls -la ~/mft-trading-bot/.github/
cat ~/mft-trading-bot/.github/DEPLOYMENT_TEST.md
```

This file should exist, proving deployment worked.

---

**Status**: Testing deployment pipeline with GitHub Secrets
