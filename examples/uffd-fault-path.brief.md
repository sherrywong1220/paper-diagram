# uffd-fault-path: figure brief

## Message
With userfaultfd, a missing-page fault is resolved in userspace: the kernel parks the faulting thread and forwards the fault through the uffd context to a handler thread, and the handler prepares the page's contents, which the kernel then copies into place.

## Reading order
The eye enters at the Main Thread (top left) and follows the steps as a loop:
- right, into the kernel, to the faulting page (①–③);
- back through the uffd context to the Handler Thread, bottom left (④–⑤);
- right again to the memory columns, where the page is filled (⑥–⑧).

The figure has three regions, left to right:
- Userspace and Kernel, split by one dotted line, with the headers flush on either side of it;
- the two memory columns, at the far right, inside the kernel's half.

## Elements
- Components:
  - Main Thread and Handler Thread, in Userspace, stacked on the left;
  - uffd context, in the Kernel, between them and the memory.
- Storage:
  - Virtual Memory, an open column (an address space);
  - Physical Memory, a closed column of frames.
- Highlights:
  - Red marks the faulting page, the frame that ends up backing it, and the fault bolt. It is the item the story is about.
  - Orange marks the handler's staging page and its frame, the source of the copy.

## Steps
1. Main Thread → `userfaultfd()` + `ioctl()` → uffd context (sync): create the descriptor and register the region. The two code labels are sloped along the arrow; the badge sits on `ioctl()`.
2. Main Thread → Access → red page in Virtual Memory (sync).
3. Fault on the red page: it has no frame (red bolt, label "Fault").
4. Red page → uffd context (sync): the kernel routes the fault to the context, and the main thread blocks.
5. uffd context → Handler Thread via `poll()` + `read()` (async, dashed): the handler picks up the fault event.
6. Handler Thread → Write → orange page in Virtual Memory (sync). An unnumbered arrow maps the orange page to its frame.
7. Handler Thread → `ioctl()` → uffd context (async, dashed): ask the kernel to resolve the fault.
8. Red page → its new frame in Physical Memory (sync): map it. A curved, unnumbered "Copy" arrow fills it from the orange frame.

## Caption
Handling page faults with userfaultfd.

Left out of the figure, for the caption or the text:
- the ioctl names (`UFFDIO_REGISTER`, `UFFDIO_COPY`);
- that the main thread stays blocked from ③ until ⑧;
- freeing the staging page.

## Assumptions
None. This is a reproduction of the reference figure; layout and arrow styles follow it.
