# template: figure brief

## Message
An application's request is served by a kernel module that touches a page on the application's behalf and reports a fault back asynchronously.

## Reading order
The eye enters at the Application (left), crosses into the Kernel to the module, follows the module's access to the address space on the right, and returns to the Application on the dashed notification. There are two regions, Userspace | Kernel, split by one dotted line, with the headers flush on either side of it.

## Elements
- Components:
  - Application, in Userspace;
  - `my_module` context, in the Kernel.
- Storage: Address Space, an open column.
- Highlights: red marks the accessed page and the fault bolt. There is no orange item.

## Steps
1. Application → Request → `my_module` context (sync).
2. `my_module` context → Access → red page in Address Space (sync).
3. Fault on the red page (red bolt, label "Fault").
4. `my_module` context → Notify → Application (async, dashed).

## Caption
A request served by a kernel module.

Left out of the figure, for the caption or the text: what the module does after notifying the application.

## Assumptions
None.
