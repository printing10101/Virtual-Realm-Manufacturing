<template>
  <div class="about-page">
    <el-card>
      <template #header>
        关于灵境制造
      </template>
      <div class="about-content">
        <h3>灵境制造 V4</h3>
        <p>版本：1.11.0</p>
        <p>基于神经逻辑网络(LNN)的智能制造AI推理与训练API服务</p>

        <el-divider />

        <h4>核心技术</h4>
        <ul>
          <li>LNN (Logical Neural Network) - 逻辑神经网络推理引擎</li>
          <li>CFC (Context-Free Grammar Network) - 快速推理模型</li>
          <li>LTC (Liquid Time Constant) - 时序数据分析模型</li>
          <li>Hybrid LNN - 多模态混合推理模型</li>
          <li>Dempster-Shafer 证据理论 - 多引擎结果融合</li>
        </ul>

        <h4>数据支撑</h4>
        <ul>
          <li>Bosch CNC 振动数据集 - 刀具状态监测</li>
          <li>Uniwear-NUAA TC4 - 钛合金磨损实验数据</li>
          <li>Uniwear-PHM2010 HRC52 - 不锈钢刀具磨损数据</li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.about-page {
  max-width: 800px;
  margin: 0 auto;
}

.about-content ul {
  padding-left: 20px;
  line-height: 1.8;
}
</style>
