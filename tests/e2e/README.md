# Shape snapshot tests

Each case is a JSON file in [cases](cases) holding every setting of a bin or baseplate, lengths in mm and angles in
degrees. Its snapshot in [snapshots](snapshots), a folder named after the case, has the shapes it built, their
fingerprints and a preview picture.

Run them in Fusion from Utilities > Add-ins with **Gridfinity tests: run**, record new snapshots with **Gridfinity
tests: update snapshots**. The commands are there when the add-in runs from a git checkout.

This page is written from the case files, run `python3 tests/e2e/write_readme.py` after adding or changing one.

## Bins

| Preview | Case | Description |
| --- | --- | --- |
| <img src="snapshots/bin_1_5x2_5x3_half_grid/preview.png" width="120" alt="bin_1_5x2_5x3_half_grid"> | [bin_1_5x2_5x3_half_grid](cases/bin_1_5x2_5x3_half_grid.json) | 1.5x2.5x3 bin on the half grid, half size feet throughout |
| <img src="snapshots/bin_1_5x2_5x3_half_size/preview.png" width="120" alt="bin_1_5x2_5x3_half_size"> | [bin_1_5x2_5x3_half_size](cases/bin_1_5x2_5x3_half_size.json) | 1.5x2.5x3 bin on the whole grid, a row of half feet along two sides, with magnet and screw holes |
| <img src="snapshots/bin_1x1x2_solid_no_lip/preview.png" width="120" alt="bin_1x1x2_solid_no_lip"> | [bin_1x1x2_solid_no_lip](cases/bin_1x1x2_solid_no_lip.json) | 1x1x2 solid bin without a lip |
| <img src="snapshots/bin_1x1x3_40mm_6mm_units/preview.png" width="120" alt="bin_1x1x3_40mm_6mm_units"> | [bin_1x1x3_40mm_6mm_units](cases/bin_1x1x3_40mm_6mm_units.json) | 1x1x3 bin on a 40 mm grid with 6 mm height units |
| <img src="snapshots/bin_1x1x3_plain/preview.png" width="120" alt="bin_1x1x3_plain"> | [bin_1x1x3_plain](cases/bin_1x1x3_plain.json) | 1x1x3 hollow bin with a lip and nothing else, the baseline the other bin cases change one thing of |
| <img src="snapshots/bin_1x4x10_creases/preview.png" width="120" alt="bin_1x4x10_creases"> | [bin_1x4x10_creases](cases/bin_1x4x10_creases.json) | 1x4x10 bin, tall and long enough for its long walls to fold in along creases |
| <img src="snapshots/bin_2_5x2_5x3_l_shape_half_size/preview.png" width="120" alt="bin_2_5x2_5x3_l_shape_half_size"> | [bin_2_5x2_5x3_l_shape_half_size](cases/bin_2_5x2_5x3_l_shape_half_size.json) | 2.5x2.5x3 L shaped bin on the whole grid, its arms end in half feet |
| <img src="snapshots/bin_2x1_base_only/preview.png" width="120" alt="bin_2x1_base_only"> | [bin_2x1_base_only](cases/bin_2x1_base_only.json) | 2x1 bin base alone, no body |
| <img src="snapshots/bin_2x1x3_body_only/preview.png" width="120" alt="bin_2x1x3_body_only"> | [bin_2x1x3_body_only](cases/bin_2x1x3_body_only.json) | 2x1x3 bin body alone, no base |
| <img src="snapshots/bin_2x1x3_deep_magnets_screws_no_grooves/preview.png" width="120" alt="bin_2x1x3_deep_magnets_screws_no_grooves"> | [bin_2x1x3_deep_magnets_screws_no_grooves](cases/bin_2x1x3_deep_magnets_screws_no_grooves.json) | 2x1x3 bin with 4.5 mm deep magnet holes and screw holes, too deep for the printability groove to fit |
| <img src="snapshots/bin_2x1x3_label_icon_text_embossed/preview.png" width="120" alt="bin_2x1x3_label_icon_text_embossed"> | [bin_2x1x3_label_icon_text_embossed](cases/bin_2x1x3_label_icon_text_embossed.json) | 2x1x3 bin with an embossed label of an icon and text |
| <img src="snapshots/bin_2x1x3_label_text_engraved/preview.png" width="120" alt="bin_2x1x3_label_text_engraved"> | [bin_2x1x3_label_text_engraved](cases/bin_2x1x3_label_text_engraved.json) | 2x1x3 bin with an engraved text label |
| <img src="snapshots/bin_2x1x3_magnets/preview.png" width="120" alt="bin_2x1x3_magnets"> | [bin_2x1x3_magnets](cases/bin_2x1x3_magnets.json) | 2x1x3 bin with magnet holes only |
| <img src="snapshots/bin_2x1x3_magnets_pull_tabs/preview.png" width="120" alt="bin_2x1x3_magnets_pull_tabs"> | [bin_2x1x3_magnets_pull_tabs](cases/bin_2x1x3_magnets_pull_tabs.json) | 2x1x3 bin with magnet holes opened to the side for pulling magnets out |
| <img src="snapshots/bin_2x1x3_magnets_pull_tabs_screws_grooves/preview.png" width="120" alt="bin_2x1x3_magnets_pull_tabs_screws_grooves"> | [bin_2x1x3_magnets_pull_tabs_screws_grooves](cases/bin_2x1x3_magnets_pull_tabs_screws_grooves.json) | 2x1x3 bin with magnet holes opened to the side, screw holes and printability grooves |
| <img src="snapshots/bin_2x1x3_magnets_screws_grooves/preview.png" width="120" alt="bin_2x1x3_magnets_screws_grooves"> | [bin_2x1x3_magnets_screws_grooves](cases/bin_2x1x3_magnets_screws_grooves.json) | 2x1x3 bin with magnet and screw holes, a printability groove bridges each magnet hole to its screw hole |
| <img src="snapshots/bin_2x1x3_screws/preview.png" width="120" alt="bin_2x1x3_screws"> | [bin_2x1x3_screws](cases/bin_2x1x3_screws.json) | 2x1x3 bin with screw holes only |
| <img src="snapshots/bin_2x1x3_shelled_notches/preview.png" width="120" alt="bin_2x1x3_shelled_notches"> | [bin_2x1x3_shelled_notches](cases/bin_2x1x3_shelled_notches.json) | 2x1x3 shelled bin with lip notches |
| <img src="snapshots/bin_2x1x3_wall_1_9/preview.png" width="120" alt="bin_2x1x3_wall_1_9"> | [bin_2x1x3_wall_1_9](cases/bin_2x1x3_wall_1_9.json) | 2x1x3 bin with 1.9 mm walls, flush with the inside of the lip, still chamfered under it |
| <img src="snapshots/bin_2x1x3_wall_2_15/preview.png" width="120" alt="bin_2x1x3_wall_2_15"> | [bin_2x1x3_wall_2_15](cases/bin_2x1x3_wall_2_15.json) | 2x1x3 bin with 2.15 mm walls, as thick as the lip wall, the first thickness without a chamfer under the lip |
| <img src="snapshots/bin_2x1x3_wall_3/preview.png" width="120" alt="bin_2x1x3_wall_3"> | [bin_2x1x3_wall_3](cases/bin_2x1x3_wall_3.json) | 2x1x3 bin with 3 mm walls, thicker than the lip |
| <img src="snapshots/bin_2x1x3_wall_3_scoop_compartments/preview.png" width="120" alt="bin_2x1x3_wall_3_scoop_compartments"> | [bin_2x1x3_wall_3_scoop_compartments](cases/bin_2x1x3_wall_3_scoop_compartments.json) | 2x1x3 bin with 3 mm walls, thicker than the lip, a scoop and 2 compartments, placed against the lip |
| <img src="snapshots/bin_2x1x4_hollow_tab_open_sides/preview.png" width="120" alt="bin_2x1x4_hollow_tab_open_sides"> | [bin_2x1x4_hollow_tab_open_sides](cases/bin_2x1x4_hollow_tab_open_sides.json) | 2x1x4 bin with a hollow tilted tab open through the side walls, engraved icon label |
| <img src="snapshots/bin_2x2x3_l_shape_half_grid/preview.png" width="120" alt="bin_2x2x3_l_shape_half_grid"> | [bin_2x2x3_l_shape_half_grid](cases/bin_2x2x3_l_shape_half_grid.json) | 2x2x3 L shaped bin on the half grid, drawn in half feet |
| <img src="snapshots/bin_2x3x5_features/preview.png" width="120" alt="bin_2x3x5_features"> | [bin_2x3x5_features](cases/bin_2x3x5_features.json) | 2x3x5 hollow bin with a scoop, lip, labelled tab, 2 compartments, magnet and screw holes |
| <img src="snapshots/bin_3x2x3_t_shape_shelled/preview.png" width="120" alt="bin_3x2x3_t_shape_shelled"> | [bin_3x2x3_t_shape_shelled](cases/bin_3x2x3_t_shape_shelled.json) | 3x2x3 T shaped shelled bin |
| <img src="snapshots/bin_3x2x4_merged_compartments/preview.png" width="120" alt="bin_3x2x4_merged_compartments"> | [bin_3x2x4_merged_compartments](cases/bin_3x2x4_merged_compartments.json) | 3x2x4 bin with a 3x2 compartment grid, two merged pockets, one of them 10 mm shallower |
| <img src="snapshots/bin_3x3x4_l_shape/preview.png" width="120" alt="bin_3x3x4_l_shape"> | [bin_3x3x4_l_shape](cases/bin_3x3x4_l_shape.json) | 3x3x4 L shaped hollow bin with a lip, no tab, one compartment, no holes |
| <img src="snapshots/bin_3x3x4_l_shape_lip_notches/preview.png" width="120" alt="bin_3x3x4_l_shape_lip_notches"> | [bin_3x3x4_l_shape_lip_notches](cases/bin_3x3x4_l_shape_lip_notches.json) | 3x3x4 L shaped bin with lip notches |
| <img src="snapshots/bin_3x3x4_l_shape_wall_1_9/preview.png" width="120" alt="bin_3x3x4_l_shape_wall_1_9"> | [bin_3x3x4_l_shape_wall_1_9](cases/bin_3x3x4_l_shape_wall_1_9.json) | 3x3x4 L shaped bin with 1.9 mm walls, flush with the inside of the lip, its chamfer under the lip follows the shape |
| <img src="snapshots/bin_3x3x4_l_shape_wall_3/preview.png" width="120" alt="bin_3x3x4_l_shape_wall_3"> | [bin_3x3x4_l_shape_wall_3](cases/bin_3x3x4_l_shape_wall_3.json) | 3x3x4 L shaped bin with 3 mm walls, thicker than the lip |

## Baseplates

| Preview | Case | Description |
| --- | --- | --- |
| <img src="snapshots/baseplate_2x2_light/preview.png" width="120" alt="baseplate_2x2_light"> | [baseplate_2x2_light](cases/baseplate_2x2_light.json) | 2x2 light baseplate without holes, the baseline the other baseplate cases change one thing of |
| <img src="snapshots/baseplate_2x2_skeletonized_padding/preview.png" width="120" alt="baseplate_2x2_skeletonized_padding"> | [baseplate_2x2_skeletonized_padding](cases/baseplate_2x2_skeletonized_padding.json) | 2x2 skeletonized baseplate with magnet sockets and uneven padding |
| <img src="snapshots/baseplate_3x2_full/preview.png" width="120" alt="baseplate_3x2_full"> | [baseplate_3x2_full](cases/baseplate_3x2_full.json) | 3x2 full baseplate with magnet sockets, screw holes and connection holes |
| <img src="snapshots/baseplate_fill_area_pieces/preview.png" width="120" alt="baseplate_fill_area_pieces"> | [baseplate_fill_area_pieces](cases/baseplate_fill_area_pieces.json) | 300x200 mm area filled with a light baseplate, cut into pieces for a 180 mm print bed, half cells, aligned left and back |
