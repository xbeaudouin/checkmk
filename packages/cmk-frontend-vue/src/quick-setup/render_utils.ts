/**
 * Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
 * This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
 * conditions defined in the file COPYING, which is part of this source code package.
 */
import { h, markRaw } from 'vue'

import CompositeWidget from '@/quick-setup/components/quick-setup/widgets/CompositeWidget.vue'
import QuickSetupStageWidgetContent from './QuickSetupStageWidgetContent.vue'

import type {
  AllValidationMessages,
  ComponentSpec,
  StageData
} from '@/quick-setup/components/quick-setup/widgets/widget_types'
import type { StageButtonSpec, VnodeOrNull } from './components/quick-setup/quick_setup_types'

export type UpdateCallback = (value: StageData) => void

export interface ButtonDefiner {
  next: (label: string) => StageButtonSpec
  prev: (label: string) => StageButtonSpec
  save: (label: string) => StageButtonSpec
}

type Callback = () => void

/**
 * Renders a component for the recap section of a completed stage
 * @param {ComponentSpec[]} recap - List of widgets to render in completed stages
 * @returns VNode | null
 */
export const renderRecap = (recap: ComponentSpec[]): VnodeOrNull => {
  if (!recap || recap.length === 0) {
    return null
  }
  return markRaw(h(CompositeWidget, { items: recap }))
}

/**
 * Renders a component for the content section of an active stage
 * @param {ComponentSpec[]} components - List of widgets to render in current stage
 * @param {UpdateCallback} onUpdate - Callback to update the stage data. It receives the whole stage data
 * @param {AllValidationMessages} formSpecErrors - Formspec Validation Errors
 * @param {StageData} userInput - The data entered previously by the user
 * @returns
 */
export const renderContent = (
  components: ComponentSpec[],
  onUpdate: UpdateCallback,
  formSpecErrors?: AllValidationMessages,
  userInput?: StageData
): VnodeOrNull => {
  if (!components || components.length === 0) {
    return null
  }

  return markRaw(
    h(QuickSetupStageWidgetContent, {
      components,
      formSpecErrors: formSpecErrors || {},
      userInput: userInput || {},
      onUpdate: onUpdate
    })
  )
}

export const defineButtons = (
  nextStageCallback: Callback,
  prevStageCallback: Callback,
  saveCallback: Callback
): ButtonDefiner => {
  const next = (label: string): StageButtonSpec => {
    return {
      label,
      variant: 'next',
      action: nextStageCallback
    }
  }

  const prev = (label: string): StageButtonSpec => {
    return {
      label,
      variant: 'prev',
      action: prevStageCallback
    }
  }

  const save = (label: string): StageButtonSpec => {
    return {
      label,
      variant: 'save',
      action: saveCallback
    }
  }

  return {
    next,
    prev,
    save
  }
}