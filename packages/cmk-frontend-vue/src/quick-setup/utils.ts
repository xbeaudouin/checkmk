/**
 * Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
 * This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
 * conditions defined in the file COPYING, which is part of this source code package.
 */

export const asStringArray = (value?: string[] | string): string[] => {
  if (!value) {
    return []
  }
  return Array.isArray(value) ? value : [value]
}
