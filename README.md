# mother-lode

Gold country in lidar, old mine maps and geology: the Mother Lode belt of
Tuolumne County, California, from Big Oak Flat and Groveland north through
Chinese Camp, Jamestown, Sonora and Columbia.

**Map:** https://brooksgroves.com/mother-lode/ ·
**Story:** https://brooksgroves.com/blog/mother-lode-post.html ·
**Picking this up?** Read [HANDOFF.md](HANDOFF.md).

Five places in bare-earth lidar (Columbia, the Harvard pit at Jamestown, the
Rawhide, Eagle-Shawmut and Big Oak Flat) and every USGS mine feature in the
county: 410 adits, 285 shafts, 345 prospect pits, 210 tailings and dump
outlines, and the named mines from the Mineral Resources Data System. What it's
built from:

1. **Every mine on the old maps.** USGS digitised every shaft, adit, prospect
   pit and tailings pile drawn on its historical topographic maps (USMIN).
2. **The ground in lidar.** Bare earth from the USGS 3DEP archive, rendered
   with the relief views from [Project Kiva](https://github.com/bdgroves/project-kiva)
   so hydraulic pits, tailings and ditches stand out.
3. **The rock underneath.** The Melones Fault Zone and the gold-bearing rocks
   along it.

Lidar coverage, checked against the 3DEP project boundaries: every gold-belt
town (Columbia, Sonora, Jamestown, Chinese Camp, Groveland, Big Oak Flat,
Soulsbyville, Tuolumne, Stent, Moccasin) sits inside two surveys,
`CA_CalaverasTuolumne_2011` and `CA_SierraNevada_12_B22`. About 72% of the
county is covered; the gaps are high country, away from the mines.

Data is fetched on GitHub Actions. Nothing here needs an API key.
