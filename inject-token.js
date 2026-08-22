// 注入 token 和权限
sessionStorage.setItem('auth_token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiIsImp0aSI6IjMyZGZjNGQ1LTRmYTItNDc0OS05ZDExLTUyOTY3NjZkNzgzYSIsImV4cCI6MTc4NzMzNDM1NiwidHlwZSI6ImFjY2VzcyJ9.F7xifQU-oLaozR1edYWKb3Wy1VkSCLYi9BS-N9Iplos');
sessionStorage.setItem('auth_user', JSON.stringify({
    "username": "admin",
    "role": "admin",
    "must_change_password": false
}));
sessionStorage.setItem('tour_completed_v1', 'true');
localStorage.setItem('tour_completed_v1', 'true');
console.log('✅ Token 已注入，刷新页面即可登录）;
