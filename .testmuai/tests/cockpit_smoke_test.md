---
mode: testing
tags: [smoke, tideflow]
---

# TideFlow Hexactine Cockpit Smoke Test

## Open cockpit and verify status bar
Open http://127.0.0.1:5173.
Verify the page heading shows TideFlow Hexactine and the Backend status pill is visible.

## Capture thought via Brain Dump modal
Click the Brain Dump button, enter "Verify smoke flow #rhythm", and click Capture Thought.
Verify the modal closes and the Focus Horizon shows Now and Next slots.

## Switch Graph Science lens
Click Communities and then PageRank on the Neo4j Graph-Science Lattice panel.
Verify a gds. Cypher preview query is visible.

## Verify Nemoclaw default-deny gate
Click Execute on the Nemoclaw Retriever panel while permissions are disabled.
Verify a Permission denied message and DENIED audit entry appear.
