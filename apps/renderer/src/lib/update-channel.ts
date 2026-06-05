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

export type UpdateChannelProvider = {
  getState: () => Promise<UpdateChannelState | null>;
  setChannel: (channel: UpdateChannel) => Promise<UpdateChannelState>;
};

export const desktopUpdateChannelProvider: UpdateChannelProvider = {
  async getState() {
    return window.minix?.getUpdateChannelState?.() ?? null;
  },
  async setChannel(channel) {
    const setUpdateChannel = window.minix?.setUpdateChannel;
    if (!setUpdateChannel) {
      throw new Error("Update channel selection is unavailable");
    }
    return setUpdateChannel(channel);
  }
};
