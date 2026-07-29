# SourceCast Demo Access

SourceCast is hosted on AWS EC2 for on-demand demos.

To keep operating costs low, the demo intentionally does not use an Elastic IP.
That means a raw `sslip.io` URL can change whenever the EC2 instance is stopped
and restarted. If an older demo link does not load, the app is not necessarily
broken; the public IP may simply have rotated.

SourceCast is currently invite-only. Contact the author for:

- the current demo URL
- demo account credentials
- a short walkthrough of the source ingestion and cited-answer workflow

This setup keeps the project affordable while still allowing the full MVP to run
when a demo is needed.
