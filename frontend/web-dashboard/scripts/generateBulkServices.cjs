const fs = require('fs');
const path = require('path');

const servicesDir = path.join(__dirname, '../src/services');

const entities = [
  { name: 'Driver', file: 'driver', endpoint: 'drivers', hasStatus: true },
  { name: 'Vehicle', file: 'vehicle', endpoint: 'vehicles', hasStatus: true },
  { name: 'Invoice', file: 'invoice', endpoint: 'invoices', hasStatus: true },
  { name: 'Document', file: 'document', endpoint: 'documents', hasStatus: true },
  { name: 'Trip', file: 'trip', endpoint: 'trips', hasStatus: true },
  { name: 'RateCard', file: 'rateCard', endpoint: 'rate-cards', hasStatus: false } // rate cards don't have a status to update in bulk right now, only bulk delete
];

for (const entity of entities) {
  const servicePath = path.join(servicesDir, `${entity.file}Service.ts`);
  if (fs.existsSync(servicePath)) {
    let content = fs.readFileSync(servicePath, 'utf-8');

    if (!content.includes('bulkDelete(ids')) {
      let newMethods = `\n  async bulkDelete(ids: string[]): Promise<void> {
    await api.post('/${entity.endpoint}/bulk-delete', { ids });
  },`;

      if (entity.hasStatus) {
        newMethods += `\n\n  async bulkUpdateStatus(ids: string[], status: string): Promise<void> {
    await api.post('/${entity.endpoint}/bulk-update-status', { ids, status });
  },`;
      }

      // Replace the last `};` with our new methods and `};`
      const lastBracketIndex = content.lastIndexOf('};');
      if (lastBracketIndex !== -1) {
        content = content.substring(0, lastBracketIndex) + newMethods + '\n};\n';
        fs.writeFileSync(servicePath, content);
        console.log(`Updated ${entity.file}Service.ts`);
      }
    }
  }
}
