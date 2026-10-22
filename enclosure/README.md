# Quota Orb enclosure, revision A

**USB on the LEFT when facing the screen.** Designed for the Heltec WiFi Kit 32 V2 with headers underneath and a **15 mm header projection allowance**. Measure the actual board before printing; this is an allowance, not a measured universal specification.

![Actual CAD render, illustrative electronics](preview/hero.png)

The enclosure uses a rounded charcoal shell, optional copper-colour accent bezel, and a separate 25-degree-backward-tilted desk cradle. The front is 65 degrees above the desk. The shell is 78 x 48 mm, 29 mm deep with its rear cover; the accent adds 0.8 mm at the front. The stand footprint is 66 x 54 mm. The complete assembly is approximately 78 x 54 x 60.1 mm.

## Print this first

**Print `05-fit-coupon.stl` first. Do not start with the complete print plate.**

1. Print the coupon with its flat front face on the bed and the PCB rails upward.
2. Place the board into it from the open rear, with the OLED toward the window. The USB must be on the left when you look at the external screen face; viewed through the open rear it appears on your right.
3. Check that the board rests on the FR4 edge supports, without forcing the glass or solder joints. Its headers must project freely through the open rear.
4. Check the OLED and both button access openings. Power it through USB and check the display at your intended viewing angle. The coupon checks these alignments; it does not reproduce the full case's recessed cable tunnel.
5. If the board rocks, a component touches a support, or a button/window is misaligned, stop before printing the shell. Revise the CAD against measured offsets.

Heltec's document gives **50.2 x 25.5 mm** in its mechanical drawing and **51 x 25.5 mm** in its specification table. This design uses a **51.6 x 26.3 mm cradle**. The active OLED area and button centres were not dimensioned precisely enough to guarantee fit from the drawing alone; the aperture and access slots are deliberately generous.

The OLED cutout is **34.6 x 20.2 mm**, exposing the glass region rather than requiring a precise active-pixel cutout. Assumed maximum front OLED stack is **5.0 mm above the PCB**, giving nominal 0.8 mm glass clearance from the front plate. The PCB rests at 8.2 mm depth; PCB thickness is assumed 1.6 mm. A 15 mm rear header projection leaves **1.2 mm** to the cover. Four tapered retainers capture the short-end corners, clear of the header rows and carriers, with 0.8 mm nominal clearance behind the PCB.

## Files

| File / folder | Purpose |
|---|---|
| `output/stl/01-front-shell.stl` | Main housing, including board cradle, nut wells, USB tunnel, button access and lettering |
| `output/stl/02-rear-cover.stl` | Removable lid, locating rim, four retainers, vents, and flush screw seats |
| `output/stl/03-desk-stand.stl` | Separate slide-in desk cradle; no stand fasteners needed |
| `output/stl/04-accent-bezel.stl` | Optional contrast-colour bezel with four locating pins |
| `output/stl/05-fit-coupon.stl` | First-print board/window/button alignment check |
| `output/stl/06-button-tool.stl` | Small plastic tool for the recessed PRG/RESET access ports |
| `output/Quota-Orb-Enclosure-RevA.3mf` | Six objects, oriented flat and arranged within 153 x 169 mm |
| `output/Quota-Orb-Enclosure-RevA.step` | Assembled four-part mechanical CAD |
| `output/step/` | Individual editable solids, in assembly orientation |
| `preview/` | Front, rear, hero and exploded CAD renders; assembly video and GIF |

All STL and 3MF dimensions are **millimetres**, at **100% scale**. STLs are already placed in print orientation with minimum Z at zero. Do not mirror them in the slicer. STEP files are in assembly coordinates, not print coordinates.

The 3MF contains geometry and object placement, without a printer-specific profile. Select your own printer and PLA profile after importing. No machine-ready G-code is supplied.

## Assembly animation

`preview/Quota-Orb-Enclosure-Assembly.mp4` is a 13-second, 1920 x 1080, 24 fps exploded/assembly render. It lifts the device from the stand, separates the bezel, board/headers, cover and screws, then assembles them in order. `preview/assembly-preview.gif` is a smaller looping preview. The electronics and fastener models are explanatory proxies; the printed parts come from the actual manufacturing meshes.

## Recommended print settings

For **PLA, FDM, 0.4 mm nozzle**:

| Setting | Starting value |
|---|---|
| Layer height | 0.20 mm |
| Walls | 4 perimeters |
| Top/bottom | At least 5 solid layers |
| Infill | 20% gyroid |
| Supports | Off initially; inspect your slicer's bridge preview |
| Material temperature | Your filament manufacturer's PLA profile |
| Body colour | Matte charcoal or black |
| Bezel colour | Copper, orange, silver, or the same PLA |

Part orientations:

- Front shell and fit coupon: external front face on the bed, interior rails up.
- Rear cover: outside rear face on the bed, tapered retainers up.
- Stand: flat foot on the bed, inclined cradle up.
- Accent: visible flat face on the bed, four locating pins up.
- Button tool: flat on the bed.

The USB tunnel roof bridges **18 mm**. PrusaSlicer completed the supplied orientations without support/stability warnings in the validation configuration, but bridge finish depends on the printer and cooling. Use local support only beneath that roof if your printer cannot bridge it cleanly. A small exterior brim is optional if PLA bed adhesion is poor. Do not enable fuzzy skin on mating surfaces, the board cradle, or the stand slot.

## Hardware

| Qty | Item |
|---:|---|
| 4 | M2.5 x 12 mm, 90-degree countersunk screws; head diameter up to 5.88 mm |
| 4 | M2.5 hex nuts, 5.0 mm across flats, approximately 2.0 mm thick |
| Optional | Four 8 mm adhesive rubber feet |
| Optional | Tiny spots of removable craft adhesive or thin double-sided tape for the cosmetic bezel |

The screw head seats are **6.4 mm diameter, 90 degrees**, intended to leave these heads flush or slightly recessed. Counter-sunk screw length includes the head. Do not substitute ordinary projecting socket/pan heads: they can obstruct the slide-in stand. No heat-set inserts, PCB drilling, or solder changes are required.

## Assembly

1. Remove print brim and strings; check the nut wells, pilot bores and cable opening. Test the nuts and screws without the electronics first. The nuts should enter without splitting the printed towers.
2. Lay the shell face down on a clean soft surface. Drop the four nuts into the deep hexagonal wells; their seats are 19 mm from the front datum.
3. Fit the board into the cradle, OLED toward the opening and USB on the left **from the screen side**. Do not press the OLED glass. Confirm that pins and solder joints clear the printed features.
4. Fit the rear cover and start all four screws by hand. Tighten only until the cover seats. The retainers capture the board; the screws must not bend the PCB or compress the display.
5. Check cable-hood clearance in the actual left-side tunnel, then power the board. The opening clears a plug; it is not a cable clamp or strain relief.
6. Fit the optional bezel using its locating pins. Its fit is intentionally loose; retain it with tiny adhesive spots if desired. Keep adhesive off the OLED. The shell also works without the cosmetic bezel.
7. Slide the enclosure down into the stand from above. The rear cover must seat against the backrest without screw-head interference. Add rubber feet if desired.
8. Check image orientation. If needed, use the existing firmware's long PRG press to flip the OLED; reach the switch through its access opening with the printed plastic tool. Confirm which opening is PRG on your physical board before using it; the other is RESET.

## What was verified

- FreeCAD 1.0.2 accepted all six parts as single valid solids.
- All exported meshes have two faces per edge and consistent winding.
- The shell, cover, bezel, stand, PCB envelope, header envelopes, screw envelopes and nut pockets have no unintended volumetric interference at the nominal CAD position.
- A geometric check confirms the USB passage exists only on the left from the front view.
- PrusaSlicer 2.9.6 imported all six objects as manifold meshes and generated toolpaths at 0.2 mm / 0.4 mm / four walls / 20% gyroid, with supports disabled and no stability warnings in the final run.
- Hero, front, rear and exploded views were rendered from the actual exported CAD meshes.

**Physical fit, printed clearances, thermal behaviour, cable tug stability and button access have not been tested on a printed enclosure.** The board and screen in the renders are illustrative proxies; they are not manufacturer-verified component models. All showcase screen images use simulated demonstration data.

## Editing

Use the supplied neutral STEP assembly or individual STEP solids in a CAD tool. The print-ready STLs and 3MF are in millimetres; STEP files use assembly coordinates. Do not mirror the parts. Generation/rendering tools and native working scenes are local development material, excluded from this runtime-focused repository.

## Sources

- [Heltec WiFi Kit 32 mechanical drawing, page 11, and specification table](https://resource.heltec.cn/download/WiFi_Kit_32/WiFi%20Kit32.pdf). The document contains mixed revision details; dimensions remain nominal until checked against the actual board.
- [Heltec V2 pinout / board photograph](https://resource.heltec.cn/download/WiFi_Kit_32/WIFI_Kit_32_pinoutDiagram_V2.pdf).
- [Accu ISO 10642 M2.5 head-envelope reference](https://www.accu.co.uk/countersunk-socket-head-screws/5414-SSK-M2-5-6-A2): 5.88 mm maximum head diameter, 1.69 mm countersunk height, 90-degree head. This is a dimensional reference, not the required screw length.

Manufacturer PDFs, STL/DWG reference downloads, private live account files, and validation G-code are excluded from the enclosure ZIP.
