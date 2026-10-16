# Calculation notes

## Commute estimate

The API performs deterministic arithmetic from explicit activity inputs and a candidate or owner-approved factor. For the demo image workflow, each assumed vehicle count is multiplied by assumed commute cycles per operating day, one-way distance, two legs per cycle, annual operating days, and the supplied factor in kg CO₂ per vehicle-km. The B3 commute endpoint calculates annual vehicle-kilometres and multiplies by a factor in kg CO₂ per vehicle-kilometre.

All supplied demo factors are labelled illustrative and unapproved. The approved factor registry is currently empty. No result should be represented as a verified campus inventory or compliance report.

## Scenario boundaries

- **Carpool:** reduces the assumed car-trip activity share; the input does not prove actual shared occupancy.
- **Campus shuttle:** reduces the selected assumed private-vehicle activity and adds the explicitly entered shuttle vehicle-kilometres and bus factor.
- **Active travel:** reduces only assumed car or motorcycle activity within the entered distance limit. Non-motorized activity has no motor-vehicle tailpipe emissions in this calculation.
- **Mode-flow display:** shows the aggregate mode profile returned by the API. Its moving symbols are decorative; they are not individual students, measured vehicles, or a traffic model.

## Evidence limits

A parking image is a single-time snapshot. A detector cannot infer daily unique commuters, trip purpose, occupancy, fuel, powertrain, or route distance from that image. Human review is still required; model readiness does not establish parking-domain accuracy. The interface and API label estimates and scenarios as illustrative, not measured or guaranteed.
