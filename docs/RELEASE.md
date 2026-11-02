# Publishing TXA on GitHub

TXA is published from Rebecca's GitHub account under the MIT licence,
the same way as The Lantern Coast. Claude cannot push from its sandbox;
these steps run on Rebecca's PC (Git and a GitHub account needed).

## The first time

1. On github.com, create an empty public repository named `txa` (no
   README, licence or .gitignore: the repository already has them).
2. In a terminal, in the folder where the repository should live:

       git clone txa-checkpoint-<version>.bundle txa
       cd txa
       git remote remove origin
       git remote add origin https://github.com/<your-account>/txa.git
       git push -u origin master --tags

   (The bundle is the one in the latest checkpoint zip. If GitHub asks
   for a password, use a personal access token, or sign in through the
   Git Credential Manager window that Git for Windows opens.)

## Each later update

Claude delivers a newer bundle; in the repository folder:

       git pull <path>/txa-checkpoint-<version>.bundle master
       git push --tags origin master

## The 1.0 release

When M7 is done, Claude tags `v1.0` and assembles the distribution
folder. On github.com, open the repository's Releases, "Draft a new
release", choose the tag `v1.0`, and attach the distribution's files:
the workbench cartridge, the sample disks, the manuals as PDF, and the
zip of everything.
