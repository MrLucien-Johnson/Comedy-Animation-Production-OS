# Production Pipeline

Every stage has an explicit `StageStatus`:

`DRAFT | READY | GENERATING | GENERATED | QA_FAILED | QA_PASSED | REQUIRES_REVIEW | APPROVED | REJECTED | SUPERSEDED | EXPORTED | LOCKED | …`

## Stages

1. IDEA  
2. EPISODE BRIEF  
3. SCRIPT  
4. DIALOGUE REVIEW  
5. STORYBOARD  
6. CONTINUITY PLAN  
7. REFERENCE RESOLUTION  
8. KEYFRAME GENERATION  
9. FRAME QA  
10. TRANSITION GENERATION  
11. FRAME QA  
12. ANIMATION PLAN  
13. ANIMATION / VIDEO ASSEMBLY  
14. VOICE / SFX / MUSIC  
15. SUBTITLES  
16. FINAL CONTINUITY QA  
17. COVER / THUMBNAIL  
18. FINAL MP4  
19. HUMAN APPROVAL  
20. PUBLISHABLE EXPORT  

## Fail closed

If continuity QA fails: mark `QA_FAILED`, repair only the needed frame, re-run QA.  
Final export requires **all required QA = PASS** or **explicit human override**.

## Honesty

Do not mark FINAL while unresolved QA remains. Engineering readiness ≠ content readiness.
