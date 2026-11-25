export type Row = Record<string, string | number | boolean | null>;

export interface Telemetry {
  checkedAt: string;
  devices: Row[];
  trend: Row[];
  invalidReadings: number;
}

export interface Loads {
  checkedAt: string;
  sources: Row[];
  tables: Row[];
  daily: Row[];
  duplicateKeys: number;
}

export interface FabricHealth {
  checkedAt: string;
  simulator: Job[];
  pipeline: Job[];
  schedules: Schedule[];
  eventstream: { name: string; sources: number; destinations: number };
}

export interface Job {
  id: string;
  status: string;
  startTimeUtc: string;
  endTimeUtc: string | null;
  failureReason?: { message?: string; errorCode?: string } | null;
}

export interface Schedule {
  id: string;
  enabled: boolean;
  configuration: {
    endDateTime: string;
    localTimeZoneId: string;
    times?: string[];
  };
}
