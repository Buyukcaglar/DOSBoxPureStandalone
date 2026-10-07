@echo off
imgmount 2 C:\BASE.VHD -t hdd -fs none -diff C:\CHILD.VHD
boot -l c
