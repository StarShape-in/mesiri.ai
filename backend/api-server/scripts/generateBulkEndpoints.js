const fs = require('fs');
const path = require('path');

const controllersDir = path.join(__dirname, '../src/controllers');
const routesDir = path.join(__dirname, '../src/routes');

const entities = [
  { name: 'Driver', file: 'driver', statusType: 'DriverStatus' },
  { name: 'Vehicle', file: 'vehicle', statusType: 'AssetStatus' },
  { name: 'Invoice', file: 'invoice', statusType: 'InvoiceStatus' },
  { name: 'Document', file: 'document', statusType: 'DocStatus' },
  { name: 'Trip', file: 'trip', statusType: 'TripStatus' },
  { name: 'RateCard', file: 'rateCard', statusType: null } // special case for is_active
];

for (const entity of entities) {
  // 1. Update Controller
  const controllerPath = path.join(controllersDir, `${entity.file}Controller.ts`);
  let controllerContent = fs.readFileSync(controllerPath, 'utf-8');

  // Prevent double injection
  if (!controllerContent.includes(`bulkDelete${entity.name}s`)) {
    let newMethods = `\n\nexport const bulkDelete${entity.name}s = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids } = req.body;

    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'No IDs provided' } });
    }

    await prisma.${entity.file === 'rateCard' ? 'rateCard' : entity.file}.updateMany({
      where: { id: { in: ids } },
      data: {
        deletedAt: new Date(),
        ${entity.file === 'rateCard' ? 'is_active' : 'isActive'}: false,
        deleted_by: userId
      }
    });
    res.json({ success: true, data: { message: \`Successfully deleted \${ids.length} ${entity.name.toLowerCase()}s\` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: \`Failed to bulk delete ${entity.name.toLowerCase()}s\` } });
  }
};\n`;

    if (entity.statusType) {
      newMethods += `\nexport const bulkUpdate${entity.name}Status = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user?.id;
    const { ids, status } = req.body;

    if (!Array.isArray(ids) || ids.length === 0 || !status) {
      return res.status(400).json({ success: false, error: { code: 'VALIDATION_ERROR', message: 'IDs and status are required' } });
    }

    await prisma.${entity.file}.updateMany({
      where: { id: { in: ids } },
      data: {
        status: status as ${entity.statusType},
        updated_by: userId
      }
    });
    res.json({ success: true, data: { message: \`Successfully updated \${ids.length} ${entity.name.toLowerCase()}s\` } });
  } catch (error) {
    res.status(500).json({ success: false, error: { code: 'SERVER_ERROR', message: \`Failed to bulk update ${entity.name.toLowerCase()}s\` } });
  }
};\n`;
    }

    fs.writeFileSync(controllerPath, controllerContent + newMethods);
    console.log(`Updated ${entity.file}Controller.ts`);
  }

  // 2. Update Route
  const routePath = path.join(routesDir, `${entity.file}Routes.ts`);
  if (fs.existsSync(routePath)) {
    let routeContent = fs.readFileSync(routePath, 'utf-8');
    if (!routeContent.includes(`bulk-delete`)) {
      // Find the import line from controller
      const importRegex = new RegExp(`import {([^}]+)} from '../controllers/${entity.file}Controller'`);
      const match = routeContent.match(importRegex);
      if (match) {
        const imports = match[1];
        let newImports = imports + `, bulkDelete${entity.name}s`;
        if (entity.statusType) {
          newImports += `, bulkUpdate${entity.name}Status`;
        }
        routeContent = routeContent.replace(importRegex, `import {${newImports}} from '../controllers/${entity.file}Controller'`);
      }

      // Find the last route and insert our bulk routes before or after
      // We will insert them right after router.use(authenticateJWT)
      let bulkRoutes = `\nrouter.post('/bulk-delete', bulkDelete${entity.name}s);\n`;
      if (entity.statusType) {
        bulkRoutes += `router.post('/bulk-update-status', bulkUpdate${entity.name}Status);\n`;
      }
      
      routeContent = routeContent.replace('router.use(authenticateJWT);', `router.use(authenticateJWT);${bulkRoutes}`);
      fs.writeFileSync(routePath, routeContent);
      console.log(`Updated ${entity.file}Routes.ts`);
    }
  }
}
