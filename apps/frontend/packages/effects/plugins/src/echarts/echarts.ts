import type {
  BarSeriesOption,
  LineSeriesOption,
  BoxplotSeriesOption,
  ScatterSeriesOption,
} from 'echarts/charts';

import type {
  DatasetComponentOption,
  GridComponentOption,
  TitleComponentOption,
  TooltipComponentOption,
} from 'echarts/components';

import type { ComposeOption } from 'echarts/core';

// 图表类型
import {
  BarChart,
  LineChart,
  PieChart,
  RadarChart,
  BoxplotChart,
  ScatterChart,
} from 'echarts/charts';

// 组件
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  TransformComponent,
} from 'echarts/components';

import * as echarts from 'echarts/core';

import { LabelLayout, UniversalTransition, LegacyGridContainLabel } from 'echarts/features';


// 渲染器
import { CanvasRenderer } from 'echarts/renderers';

// ComposeOption 类型扩展：加入 boxplot + scatter
export type ECOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | BoxplotSeriesOption
  | ScatterSeriesOption
  | DatasetComponentOption
  | GridComponentOption
  | TitleComponentOption
  | TooltipComponentOption
>;

// 注册组件（新增 BoxplotChart + ScatterChart）
echarts.use([
  TitleComponent,
  PieChart,
  RadarChart,
  TooltipComponent,
  GridComponent,
  DatasetComponent,
  TransformComponent,
  BarChart,
  LineChart,
  BoxplotChart,   // <<< 必须
  ScatterChart,   // <<< boxplot 的 outlier 依赖它
  LabelLayout,
  UniversalTransition,
  CanvasRenderer,
  LegendComponent,
  ToolboxComponent,
  LegacyGridContainLabel,
]);

export default echarts;
