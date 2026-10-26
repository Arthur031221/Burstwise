# Sample photo credits

`examples/make_sample.py` downloads four videos from Wikimedia Commons and cuts still frames
from them. The frames are not stored in this repository. Capture times in the frames are
generated, because video has no EXIF. The frames are derived data, so each keeps the licence
of its source video. The script is MIT like the rest of the project.

| Scene | Source file | Author | Licence |
| --- | --- | --- | --- |
| singer | Song sung during marriage ceremony in Arebashe.webm | Yakshitha | CC BY-SA 4.0 |
| finch | Carduelis sinica bathing and flying x40 slowmotion.webm | Phonon.b | CC BY-SA 4.0 |
| cat | Cat Play 03.webm | NairobiPapel and Kamaa | CC BY-SA 4.0 |
| grad | Graduation Ceremony (1008568).webm | US Navy | Public domain |

The live demo shows downscaled copies of these frames under the same terms.

The benchmark in `bench/run.py` uses four large JPEG files from Wikimedia Commons and three RAW
files from raw.pixls.us. All of them are CC0. They are downloaded when you run the script and
are not stored here.
