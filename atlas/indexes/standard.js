// Ordinary indexes + TTL + time series. Run against the Atlas sandbox once.
db.events.createIndex({ created_at: 1 }, { expireAfterSeconds: 172800 });   // L0 decay (48h)
db.events.createIndex({ sprint: 1, agent: 1, created_at: -1 });

db.tickets.createIndex({ status: 1, priority: -1, created_at: 1 });          // claim scan
db.tickets.createIndex({ lease_until: 1 }, { sparse: true });               // reaper
db.tickets.createIndex({ deps: 1 });                                        // frontier / $graphLookup

db.agents.createIndex({ heartbeat_at: 1 });
db.decisions.createIndex({ caused_by: 1 });                                 // provenance traversal
db.playbooks.createIndex({ ticket_class: 1, version: -1 });
db.artifacts.createIndex({ ticket_id: 1 });
db.verdicts.createIndex({ ticket_id: 1, created_at: -1 });

// metrics must be created as a time series collection:
// db.createCollection("metrics", {
//   timeseries: { timeField: "ts", metaField: "meta", granularity: "seconds" }
// });
