# Outbound action approval

Every public platform message is represented as an `OutboundAction` with a platform, target, bounded text, evidence IDs, and status. The only valid transition to sending is:

`proposed -> approved -> sent`

An operator may edit the text while approving. Rejected, sent, or already-reviewed actions cannot be approved or rejected again. `OutboundActionService` records proposal, approval, rejection, and send audit entries.

The send endpoint refuses unconfigured platforms and the sender refuses actions that are not approved. Private memory is never copied into an action automatically; any generated suggestion must pass recipient and disclosure policy before it is proposed.

Platform reply generation is operator-triggered from an event ID. The generated response is addressed to `viewer_direct`, uses only the stream-safe profile projection, and retains the source event ID as evidence on the action.
