<template>
  <div class="about-page">
    <el-card>
      <template #header>
        {{ $t('about.pageTitle') }}
      </template>
      <div class="about-content">
        <h3>{{ $t('about.productName') }}</h3>
        <p>{{ $t('about.version') }}</p>
        <p>{{ $t('about.description') }}</p>

        <el-divider />

        <h4>{{ $t('about.coreTech') }}</h4>
        <ul>
          <li>{{ $t('about.techLnn') }}</li>
          <li>{{ $t('about.techCfc') }}</li>
          <li>{{ $t('about.techLtc') }}</li>
          <li>{{ $t('about.techHybrid') }}</li>
          <li>{{ $t('about.techDempster') }}</li>
        </ul>

        <h4>{{ $t('about.dataSupport') }}</h4>
        <ul>
          <li>{{ $t('about.dataBosch') }}</li>
          <li>{{ $t('about.dataUniwearTc4') }}</li>
          <li>{{ $t('about.dataUniwearPhm') }}</li>
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
