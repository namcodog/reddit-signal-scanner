## Monitoring & Frontend Fixes (Sept 17)
- monitoring `/monitoring/stats` lacked null handling, causing 24h script to log `null`. Updated script to default missing fields to 0/"unknown" so it keeps running even if backend down.
- frontend `toggleV2Algorithm` now posts `enable` and `split`, interprets response `{enable, split}`. UI refreshes signal and monitoring after toggle.
- AB config normalization: `getV2Config` returns `v2_enabled`, `v2_percentage`, `current_algorithm` values derived from backend fields.
- Need follow-up: Decision panel still mixes tradeable=false with strong directional cues; plan to adjust UI to show neutral messaging when gate blocks a trade.
