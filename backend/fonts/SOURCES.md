## YouTube Shorts Font Research

The following fonts were added based on commonly recommended high-impact YouTube title/thumbnail styles (bold sans-serif and expressive display fonts).

Reference used:
- https://www.designyourway.net/blog/best-fonts-for-youtube-thumbnails/

Added fonts (Google Fonts):
- Anton-Regular.ttf
- BebasNeue-Regular.ttf
- Oswald-Variable-wght.ttf
- Poppins-ExtraBold.ttf
- Raleway-Variable-wght.ttf
- Montserrat-Variable-wght.ttf
- Bangers-Regular.ttf
- Roboto.ttf
- OpenSans.ttf
- ArchivoBlack-Regular.ttf
- LeagueSpartan.ttf
- BarlowCondensed-Bold.ttf
- Urbanist.ttf
- Sora.ttf
- Inter.ttf
- NunitoSans.ttf
- Rubik.ttf
- WorkSans.ttf
- DMSans.ttf

Download sources:
- https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-ExtraBold.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/raleway/Raleway%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/bangers/Bangers-Regular.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/roboto/Roboto%5Bwdth,wght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/opensans/OpenSans%5Bwdth,wght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/archivoblack/ArchivoBlack-Regular.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/leaguespartan/LeagueSpartan%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/barlowcondensed/BarlowCondensed-Bold.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/urbanist/Urbanist%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/sora/Sora%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/nunitosans/NunitoSans%5BYTLC,opsz,wdth,wght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/rubik/Rubik%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/worksans/WorkSans%5Bwght%5D.ttf
- https://raw.githubusercontent.com/google/fonts/main/ofl/dmsans/DMSans%5Bopsz,wght%5D.ttf

Notes:
- Arial and Helvetica are not bundled because they are proprietary system fonts, not redistributable Google Fonts files.

## TikTok Sans Bold (static)

`TikTokSans-Bold.ttf` is a static instance of `TikTokSans-Regular.ttf` (the
variable font, whose default instance is Light/300) pinned at `wght=700,
wdth=100, opsz=36, slnt=0` with fontTools `varLib.instancer`, renamed to family
"TikTok Sans" / style "Bold". libass renders a variable font's default instance,
so captions need the static file to get real bold TikTok Sans.
Source: https://fonts.google.com/specimen/TikTok+Sans (OFL).

## Nunito Sans Bold (static caption face)

`NunitoSans.ttf` now contains the static Bold/700 face (97,276 bytes),
copied from the locally installed `NunitoSans-Bold.ttf`. The font's embedded
copyright and license metadata are preserved. Source family: Google Fonts,
https://fonts.google.com/specimen/Nunito+Sans (SIL Open Font License).
SHA-256: ba358d29576c727a7ba49e257c25c7ac9f5bb2dd411000f47da5c7a29eb246e9.
The stable API name remains `NunitoSans`. The previous variable file's default
ExtraLight instance did not render the bold weight shown in the browser preview.
