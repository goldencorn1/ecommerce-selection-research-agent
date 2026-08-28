# 思考块设计系统规范

## 🎯 设计目标

确保思考块组件与整个应用的设计语言保持完全一致，提供统一的用户体验。

## 📐 设计规范

### 字体系统
```css
/* 标题字体 - 与 CardTitle 保持一致 */
font-weight: 600; /* font-semibold */
line-height: 1; /* leading-none */
```

### 尺寸规范
```css
/* 图标尺寸 */
icon-size: 18px; /* 与文字比例协调 */

/* 内边距 */
padding: 1.5rem; /* px-6 py-4 */

/* 外边距 */
margin-bottom: 1.5rem; /* mb-6 */

/* 圆角 */
border-radius: 0.75rem; /* rounded-xl */
```

### 颜色系统

#### 思考阶段（活跃状态）
```css
/* 边框和背景 */
border-color: hsl(var(--primary) / 0.2);
background-color: hsl(var(--primary) / 0.05);

/* 图标和文字 */
color: hsl(var(--primary));

/* 阴影 */
box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
```

#### 完成阶段（静态状态）
```css
/* 边框和背景 */
border-color: hsl(var(--border));
background-color: hsl(var(--card));

/* 图标 */
color: hsl(var(--muted-foreground));

/* 文字 */
color: hsl(var(--foreground));
```

#### 内容区域
```css
/* 思考阶段 */
.prose-primary {
  color: hsl(var(--primary));
}

/* 完成阶段 */
.opacity-80 {
  opacity: 0.8;
}
```

### 交互状态
```css
/* 悬停状态 */
.hover\:bg-accent:hover {
  background-color: hsl(var(--accent));
}

.hover\:text-accent-foreground:hover {
  color: hsl(var(--accent-foreground));
}
```

## 🔄 状态变化

### 状态映射
| 状态 | 边框 | 背景 | 图标颜色 | 文字颜色 | 阴影 |
|------|------|------|----------|----------|------|
| 思考中 | primary/20 | primary/5 | primary | primary | 有 |
| 已完成 | border | card | muted-foreground | foreground | 无 |

### 动画过渡
```css
transition: all 200ms ease-in-out;
```

## 📱 响应式设计

### 间距适配
- 移动端：保持相同的内边距比例
- 桌面端：标准的 `px-6 py-4` 内边距

### 字体适配
- 所有设备：保持 `font-semibold` 字体权重
- 图标尺寸：固定 18px，确保清晰度

## 🎨 与现有组件的对比

### CardTitle 对比
| 属性 | CardTitle | ThoughtBlock |
|------|-----------|--------------|
| 字体权重 | font-semibold | font-semibold ✅ |
| 行高 | leading-none | leading-none ✅ |
| 颜色 | foreground | primary/foreground |

### Card 对比
| 属性 | Card | ThoughtBlock |
|------|------|--------------|
| 圆角 | rounded-lg | rounded-xl |
| 边框 | border | border ✅ |
| 背景 | card | card/primary ✅ |

### Button 对比
| 属性 | Button | ThoughtBlock Trigger |
|------|--------|---------------------|
| 内边距 | 标准 | px-6 py-4 ✅ |
| 悬停 | hover:bg-accent | hover:bg-accent ✅ |
| 圆角 | rounded-md | rounded-xl |

## ✅ 设计检查清单

### 视觉一致性
- [ ] 字体权重与 CardTitle 一致
- [ ] 圆角设计与卡片组件统一
- [ ] 颜色使用 CSS 变量系统
- [ ] 间距符合设计规范

### 交互一致性
- [ ] 悬停状态与 Button 组件一致
- [ ] 过渡动画时长统一（200ms）
- [ ] 状态变化平滑自然

### 可访问性
- [ ] 颜色对比度符合 WCAG 标准
- [ ] 图标尺寸适合点击/触摸
- [ ] 状态变化有明确的视觉反馈

## 🔧 实现要点

1. **使用设计系统变量**: 所有颜色都使用 CSS 变量，确保主题切换正常
2. **保持组件一致性**: 与现有 Card、Button 组件的样式保持一致
3. **响应式友好**: 在不同设备上都有良好的显示效果
4. **性能优化**: 使用 CSS 过渡而非 JavaScript 动画

这个设计系统确保了思考块组件与整个应用的视觉语言完全统一，提供了一致的用户体验。
