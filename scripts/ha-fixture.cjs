const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');

const inventoryPath = path.join(__dirname, '..', 'fixtures', 'ha', 'north-room.yaml');
const inventory = yaml.load(fs.readFileSync(inventoryPath, 'utf8'));
if (!Array.isArray(inventory.areas) || !Array.isArray(inventory.devices) || !Array.isArray(inventory.entities)) {
  throw new Error('Invalid synthetic home inventory.');
}
const byId = new Map();
const areaNames = new Map(inventory.areas.map((area) => [area.id, area.name]));
for (const entity of inventory.entities) {
  if (!entity.id || !entity.name || byId.has(entity.id)) throw new Error('Invalid or duplicate fixture entity ID.');
  byId.set(entity.id, entity);
}

function stateRecord(entity) {
  const attrs = { ...(entity.attributes || {}), friendly_name: entity.name };
  if (entity.id.startsWith('climate.')) {
    attrs.temperature = attrs.target_temperature;
    delete attrs.target_temperature;
    attrs.hvac_modes = attrs.hvac_modes || ['heat', 'off'];
    delete attrs.supported_features;
    delete attrs.unit_of_measurement;
  }
  return { entity_id: entity.id, state: String(entity.state ?? 'unknown'), attributes: attrs };
}

module.exports = { inventory, byId, areaNames, stateRecord };
