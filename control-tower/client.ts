import { RayfinClient, resolveRayfinConfig } from '@microsoft/rayfin-client';
import { browserSession } from '@microsoft/rayfin-auth';
import { functionsService } from '@microsoft/rayfin-functions';
import { connectorsService } from '@microsoft/rayfin-connectors';
import { fabricSemanticModel, type FabricSemanticModel, type QueryTable } from '@microsoft/rayfin-connector-fabric-semanticmodel';
import { connectorConfig } from '../rayfin/connectors/plantmodel/schema';
import type { AppFunctionsSchema } from '../rayfin/functions/src/types';
import type { Row } from '../rayfin/functions/src/contracts';

type AppConnectorsSchema = { plantmodel: FabricSemanticModel<'executeQuery'> };

export async function connect() {
  const env = import.meta.env.RAYFIN ?? {};
  const config = await resolveRayfinConfig({
    apiUrl: env.RAYFIN_PUBLIC_API_URL,
    publishableKey: env.RAYFIN_PUBLIC_PUBLISHABLE_KEY,
  });
  if (typeof config.baseUrl !== 'string' || !config.publishableKey?.trim()) {
    throw new Error('Rayfin deployment configuration is missing. Deploy this app with rayfin up before opening it.');
  }
  const projectId = env.RAYFIN_PUBLIC_ITEM_ID;
  if (!projectId) throw new Error('Fabric app item ID is missing from the deployment configuration.');
  const client = RayfinClient.create({
    baseUrl: config.baseUrl, publishableKey: config.publishableKey,
    runtimeConfig: config.runtimeConfig,
    auth: browserSession({ storage: true }),
    services: {
      functions: functionsService<AppFunctionsSchema>(),
      connectors: connectorsService<AppConnectorsSchema>({
        configs: { plantmodel: connectorConfig },
        runtime: { plantmodel: fabricSemanticModel() },
      }),
    },
  });
  return {
    client,
    fabricOptions: {
      workspaceId: '6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23', projectId,
      fabricPortalUrl: 'https://app.fabric.microsoft.com',
      returnOrigin: window.location.origin,
    },
  };
}

export type Connection = Awaited<ReturnType<typeof connect>>;

export function modelRows(table: QueryTable): Row[] {
  return table.rows.map(cells => Object.fromEntries(table.columns.map((column, i) => {
    const value = cells[i];
    if (value !== null && typeof value !== 'string' && typeof value !== 'number' && typeof value !== 'boolean') {
      throw new Error(`Unexpected semantic model result in ${column.name}.`);
    }
    return [column.name.replace(/^.*\[/, '').replace(/\]$/, ''), value];
  })));
}
