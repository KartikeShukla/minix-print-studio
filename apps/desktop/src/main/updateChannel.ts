import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

export type UpdateChannel = "stable" | "beta";

export type UpdateChannelState = {
  channel: UpdateChannel;
  availableChannels: UpdateChannel[];
  updatedAt: string;
  appVersion: string;
  autoUpdate: {
    enabled: boolean;
    reason: string;
  };
};

type UpdateChannelOptions = {
  userDataPath: string;
  appVersion: string;
  now?: Date;
};

type SetUpdateChannelOptions = UpdateChannelOptions & {
  channel: string;
};

const AVAILABLE_CHANNELS: UpdateChannel[] = ["stable", "beta"];
const UPDATE_CHANNEL_FILE = path.join("settings", "update-channel.json");
const AUTO_UPDATE_DISABLED_REASON =
  "Auto-updates are disabled until signed release publishing is configured.";

export function getUpdateChannelState({
  userDataPath,
  appVersion,
  now = new Date()
}: UpdateChannelOptions): UpdateChannelState {
  const stored = readStoredChannel(userDataPath);
  return buildState({
    channel: stored?.channel ?? "stable",
    updatedAt: stored?.updatedAt ?? now.toISOString(),
    appVersion
  });
}

export function setUpdateChannel({
  userDataPath,
  channel,
  appVersion,
  now = new Date()
}: SetUpdateChannelOptions): UpdateChannelState {
  const normalizedChannel = normalizeUpdateChannel(channel);
  const updatedAt = now.toISOString();
  const settingsPath = getUpdateChannelPath(userDataPath);

  mkdirSync(path.dirname(settingsPath), { recursive: true });
  writeFileSync(
    settingsPath,
    `${JSON.stringify({ channel: normalizedChannel, updatedAt }, null, 2)}\n`,
    "utf8"
  );

  return buildState({
    channel: normalizedChannel,
    updatedAt,
    appVersion
  });
}

function buildState({
  channel,
  updatedAt,
  appVersion
}: {
  channel: UpdateChannel;
  updatedAt: string;
  appVersion: string;
}): UpdateChannelState {
  return {
    channel,
    availableChannels: AVAILABLE_CHANNELS,
    updatedAt,
    appVersion,
    autoUpdate: {
      enabled: false,
      reason: AUTO_UPDATE_DISABLED_REASON
    }
  };
}

function readStoredChannel(userDataPath: string): { channel: UpdateChannel; updatedAt: string } | null {
  const settingsPath = getUpdateChannelPath(userDataPath);
  if (!existsSync(settingsPath)) {
    return null;
  }

  try {
    const parsed = JSON.parse(readFileSync(settingsPath, "utf8")) as {
      channel?: unknown;
      updatedAt?: unknown;
    };
    if (typeof parsed.channel !== "string" || typeof parsed.updatedAt !== "string") {
      return null;
    }
    return {
      channel: normalizeUpdateChannel(parsed.channel),
      updatedAt: parsed.updatedAt
    };
  } catch {
    return null;
  }
}

function normalizeUpdateChannel(channel: string): UpdateChannel {
  if (channel === "stable" || channel === "beta") {
    return channel;
  }
  throw new Error(`Unsupported update channel: ${channel}`);
}

function getUpdateChannelPath(userDataPath: string): string {
  return path.join(userDataPath, UPDATE_CHANNEL_FILE);
}
