# My safety planning notes to ensure that untrusted pdfs are still safe to use in Research Marker

## Untrusted PDFs - maybe someone wants to read a paper but source could have been compromised/put malware in the pdf. We need to protect against these issues and make the app as safe to use as possible.

### Safety features

User facing controls: 
- optional safety check at upload time (box for the user to check for malware scanning)

- optional safety mechanisms at read/open time (i.e. user can open the pdf is safe mode or they can just open it raw if its from a trusted source)
    - default is set in upload modal
    - in settings modal they can change default open mode between safe and raw. This will switch files between sanitized and raw.
        - honestly settings should have full data - timestamp, scanner status, rescan options, recreate safe pdf, etc.
    - save files in different folders - raw and safe and change loading paths based on open mode.
    - animations/notifications for when processing files for safe mode use.
    - error handling for when safe mode fails to process a file.
    - explain what safe mode does and that it can remove functionality (i.e. js) and can potentially mess up rendering.
        - probably unecessary if you get pdfs from a trusted source (i.e. arxiv).
- notifications for anything important

- shouldn't add any clunkiness to UI/UX. It should be as seamless as possible.

Backend/Internal features:

Research marker should not have any permissions to write to the user's system (outside of the script running worker, which should spin down as soon as all scripts are completed)

The renderer should have literally no permissions (write, network, etc.) - should prevent most malicious content from being executed.   

Malware scanning before first open:
- Some sort of clamscam/malware scan to check the pdf for malicous content.     
    - if scan comes back positive, we should not allow the user to use the pdf and we should inform them.
        - use anyway button though so they can still open the pdf.

Safe mode when opening pdf for reading:
- notes should be same across both modes
- rebuild 