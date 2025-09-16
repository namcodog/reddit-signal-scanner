/**
 * 响应式图片组件 - v0级别性能优化
 * 特点：懒加载、响应式源、渐进式加载、错误处理
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';
import { ImageIcon } from 'lucide-react';

interface ResponsiveImageProps {
  src: string;
  alt: string;
  srcSet?: {
    mobile?: string;
    tablet?: string;
    desktop?: string;
    highDpi?: string; // 高分屏
  };
  className?: string;
  loading?: 'lazy' | 'eager';
  onLoad?: () => void;
  onError?: (error: string) => void;
  placeholder?: React.ReactNode;
  fallback?: React.ReactNode;
  aspectRatio?: string; // CSS aspect-ratio
}

const ResponsiveImage: React.FC<ResponsiveImageProps> = ({
  src,
  alt,
  srcSet,
  className = '',
  loading = 'lazy',
  onLoad,
  onError,
  placeholder,
  fallback,
  aspectRatio,
}) => {
  const { type, pixelRatio } = useDeviceDetection();
  const [loadState, setLoadState] = useState<'loading' | 'loaded' | 'error'>('loading');
  const [isVisible, setIsVisible] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 根据设备类型和像素比选择最佳图片源
  const getOptimalImageSrc = useCallback((): string => {
    if (!srcSet) return src;
    
    // 高分屏优先
    if (pixelRatio >= 2 && srcSet.highDpi) {
      return srcSet.highDpi;
    }
    
    // 根据设备类型选择
    switch (type) {
      case 'mobile':
        return srcSet.mobile || src;
      case 'tablet':
        return srcSet.tablet || srcSet.desktop || src;
      case 'desktop':
        return srcSet.desktop || src;
      default:
        return src;
    }
  }, [src, srcSet, type, pixelRatio]);

  // 图片加载成功处理
  const handleImageLoad = useCallback((): void => {
    setLoadState('loaded');
    onLoad?.();
  }, [onLoad]);

  // 图片加载失败处理
  const handleImageError = useCallback((): void => {
    setLoadState('error');
    onError?.('图片加载失败');
  }, [onError]);

  // Intersection Observer 实现懒加载
  useEffect(() => {
    if (loading !== 'lazy' || !containerRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            observer.disconnect();
          }
        });
      },
      { 
        rootMargin: '50px', // 提前50px开始加载
        threshold: 0.1 
      }
    );

    observer.observe(containerRef.current);

    return () => observer.disconnect();
  }, [loading]);

  // 渐进式图片加载
  useEffect(() => {
    if (!imgRef.current) return;
    
    if (loading === 'eager' || isVisible) {
      const img = imgRef.current;
      img.src = getOptimalImageSrc();
    }
  }, [loading, isVisible, getOptimalImageSrc]);

  // 渲染占位符
  const renderPlaceholder = (): React.ReactNode => {
    if (placeholder) return placeholder;
    
    return (
      <div className={`
        flex items-center justify-center bg-gray-100
        ${aspectRatio ? '' : 'aspect-video'}
      `}>
        <ImageIcon className="w-8 h-8 text-gray-400 animate-pulse" />
      </div>
    );
  };

  // 渲染错误状态
  const renderError = (): React.ReactNode => {
    if (fallback) return fallback;
    
    return (
      <div className={`
        flex items-center justify-center bg-gray-100 border border-gray-200 rounded-md
        ${aspectRatio ? '' : 'aspect-video'}
      `}>
        <div className="text-center">
          <ImageIcon className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500">加载失败</p>
        </div>
      </div>
    );
  };

  return (
    <div 
      ref={containerRef}
      className={`relative overflow-hidden ${className}`}
      style={{
        aspectRatio: aspectRatio || undefined,
      }}
    >
      {/* 加载状态 */}
      {loadState === 'loading' && renderPlaceholder()}
      
      {/* 错误状态 */}
      {loadState === 'error' && renderError()}
      
      {/* 图片 */}
      <img
        ref={imgRef}
        alt={alt}
        className={`
          w-full h-full object-cover transition-opacity duration-300
          ${loadState === 'loaded' ? 'opacity-100' : 'opacity-0'}
        `}
        onLoad={handleImageLoad}
        onError={handleImageError}
        loading={loading}
        decoding="async"
      />
    </div>
  );
};

export default ResponsiveImage;