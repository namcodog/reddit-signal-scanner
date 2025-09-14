/**
 * 页面过渡动画组件
 * 简洁优雅的淡入淡出效果，不依赖外部库
 */

import React, { useEffect, useState, useRef } from 'react';
import { useLocation } from 'react-router-dom';

interface PageTransitionProps {
  children: React.ReactNode;
}

const PageTransition: React.FC<PageTransitionProps> = ({ children }) => {
  const location = useLocation();
  const [isVisible, setIsVisible] = useState(true);
  const previousPathnameRef = useRef(location.pathname);
  
  useEffect(() => {
    const currentPathname = location.pathname;
    const previousPathname = previousPathnameRef.current;
    
    if (previousPathname !== currentPathname) {
      // 更新ref，但不会触发重新渲染
      previousPathnameRef.current = currentPathname;
      
      // 页面切换时的动画效果
      setIsVisible(false);
      
      const timer = setTimeout(() => {
        setIsVisible(true);
      }, 150);
      
      return () => {
        clearTimeout(timer);
      };
    }
  }, [location.pathname]);
  
  return (
    <div 
      className={`
        page-transition-container
        transition-all duration-300 ease-in-out
        ${isVisible 
          ? 'opacity-100 translate-y-0' 
          : 'opacity-0 translate-y-2'
        }
      `}
    >
      {children}
    </div>
  );
};

export default PageTransition;