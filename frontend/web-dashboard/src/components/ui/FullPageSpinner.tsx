export default function FullPageSpinner() {
  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#F5F5F7',
    }}>
      <div style={{
        width: 40,
        height: 40,
        border: '3px solid #F0F0F2',
        borderTopColor: '#E8450F',
        borderRadius: '50%',
        animation: 'spin 0.7s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
