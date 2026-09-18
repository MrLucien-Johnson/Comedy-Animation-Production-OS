# Exports

## FFmpeg assembly

`assemble_slideshow` builds a simple MP4 from stills when QA passes or human override is set.

## Aspects

Master is **1:1**. Additional exports use **crop/reframe metadata**, never stretch:

- 1:1 master  
- 9:16 short-form  
- 16:9  
- 4:5  

## Covers

Every episode supports master / square / vertical / thumbnail covers. Titles composited programmatically, e.g.:

```text
LIKKLE JAY
SEASON 1, EPISODE 2
DI COOKIE JAR
```

## Prerequisites

Missing frames, failed QA, or missing ffmpeg → export reports failure honestly.
