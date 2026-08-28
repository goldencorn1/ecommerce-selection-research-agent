// Next.js/webpack treats a regular-file readlink EISDIR result as fatal on
// some Windows Node runtimes. Normalize it to EINVAL, which their tracing
// code already treats as "not a symlink". Linux and macOS are untouched.
// @ts-nocheck -- this is a small CommonJS bootstrap that monkey-patches Node's
// overloaded fs APIs before Next.js starts; Next owns the runtime typings.
const fs = require("node:fs");

if (process.platform === "win32") {
  const normalize = (error) => {
    if (error && error.code === "EISDIR") {
      error.code = "EINVAL";
      error.errno = -22;
    }
    return error;
  };

  const readlink = fs.readlink;
  fs.readlink = (...args) => {
    const callback = args.pop();
    return readlink.call(fs, ...args, (error, target) => callback(normalize(error), target));
  };

  const readlinkSync = fs.readlinkSync;
  fs.readlinkSync = (...args) => {
    try {
      return readlinkSync.call(fs, ...args);
    } catch (error) {
      throw normalize(error);
    }
  };

  const readlinkPromise = fs.promises.readlink;
  fs.promises.readlink = async (...args) => {
    try {
      return await readlinkPromise.call(fs.promises, ...args);
    } catch (error) {
      throw normalize(error);
    }
  };
}

require("next/dist/bin/next");
